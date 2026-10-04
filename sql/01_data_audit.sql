WITH item_totals AS (
    SELECT
        order_id,
        SUM(price::numeric) AS merchandise_value,
        SUM(freight_value::numeric) AS freight_value
    FROM raw.order_items
    GROUP BY order_id
),
payment_totals AS (
    SELECT
        order_id,
        SUM(payment_value::numeric) AS paid_value
    FROM raw.order_payments
    GROUP BY order_id
)
SELECT
    COUNT(*) AS total_orders,
    COUNT(*) FILTER (
        WHERE i.order_id IS NULL
    ) AS orders_without_items,
    COUNT(*) FILTER (
        WHERE p.order_id IS NULL
    ) AS orders_without_payments,
    COUNT(*) FILTER (
        WHERE i.order_id IS NOT NULL
          AND p.order_id IS NOT NULL
          AND ABS(
              i.merchandise_value + i.freight_value - p.paid_value
          ) > 0.01
    ) AS orders_with_payment_difference,
    COUNT(*) FILTER (
        WHERE o.order_status = 'delivered'
          AND o.order_delivered_customer_date IS NULL
    ) AS delivered_without_delivery_date,
    COUNT(*) FILTER (
        WHERE o.order_delivered_customer_date::timestamp
            < o.order_purchase_timestamp::timestamp
    ) AS delivery_before_purchase
FROM raw.orders o
LEFT JOIN item_totals i ON o.order_id = i.order_id
LEFT JOIN payment_totals p ON o.order_id = p.order_id;

-- Check missing items, missing payments, and payment differences by status.

WITH items AS (
    SELECT
        order_id,
        SUM(price::numeric + freight_value::numeric) AS expected_total
    FROM raw.order_items
    GROUP BY order_id
),
payments AS (
    SELECT
        order_id,
        SUM(payment_value::numeric) AS paid_total
    FROM raw.order_payments
    GROUP BY order_id
)
SELECT
    o.order_status,
    COUNT(*) AS total_orders,
    COUNT(*) FILTER (
        WHERE i.order_id IS NULL
    ) AS without_items,
    COUNT(*) FILTER (
        WHERE p.order_id IS NULL
    ) AS without_payments,
    COUNT(*) FILTER (
        WHERE ABS(p.paid_total - i.expected_total) > 0.01
    ) AS payment_difference_orders,
    ROUND(
        MAX(ABS(p.paid_total - i.expected_total)), 2
    ) AS largest_absolute_difference
FROM raw.orders o
LEFT JOIN items i ON o.order_id = i.order_id
LEFT JOIN payments p ON o.order_id = p.order_id
GROUP BY o.order_status
ORDER BY total_orders DESC;

-- Inspect the largest payment differences and missing payments.
WITH items AS (
    SELECT
        order_id,
        COUNT(*) AS item_count,
        SUM(price::numeric) AS merchandise_value,
        SUM(freight_value::numeric) AS freight_value
    FROM raw.order_items
    GROUP BY order_id
),
payments AS (
    SELECT
        order_id,
        COUNT(*) AS payment_count,
        STRING_AGG(DISTINCT payment_type, ', ') AS payment_types,
        SUM(payment_value::numeric) AS paid_total
    FROM raw.order_payments
    GROUP BY order_id
),
audit AS (
    SELECT
        o.order_id,
        o.order_status,
        i.item_count,
        p.payment_count,
        p.payment_types,
        i.merchandise_value,
        i.freight_value,
        i.merchandise_value + i.freight_value AS expected_total,
        p.paid_total,
        p.paid_total
            - (i.merchandise_value + i.freight_value) AS difference
    FROM raw.orders o
    JOIN items i ON o.order_id = i.order_id
    LEFT JOIN payments p ON o.order_id = p.order_id
)
SELECT *
FROM audit
WHERE payment_count IS NULL
   OR ABS(difference) > 0.01
ORDER BY ABS(difference) DESC NULLS FIRST, order_id
LIMIT 21;

-- Compare reconciliation differences by payment type and installments.
WITH items AS (
    SELECT
        order_id,
        SUM(price::numeric + freight_value::numeric) AS expected_total
    FROM raw.order_items
    GROUP BY order_id
),
payments AS (
    SELECT
        order_id,
        COUNT(*) AS payment_count,
        MAX(payment_type) AS payment_type,
        MAX(payment_installments::integer) AS installments,
        SUM(payment_value::numeric) AS paid_total
    FROM raw.order_payments
    GROUP BY order_id
)
SELECT
    p.payment_type,
    p.installments,
    COUNT(*) AS orders_checked,
    COUNT(*) FILTER (
        WHERE p.paid_total - i.expected_total > 0.01
    ) AS payments_above,
    COUNT(*) FILTER (
        WHERE p.paid_total - i.expected_total < -0.01
    ) AS payments_below,
    ROUND(
        AVG(p.paid_total - i.expected_total)
            FILTER (
                WHERE ABS(p.paid_total - i.expected_total) > 0.01
            ),
        2
    ) AS average_difference_flagged
FROM items i
JOIN payments p ON i.order_id = p.order_id
WHERE p.payment_count = 1
GROUP BY p.payment_type, p.installments
HAVING COUNT(*) FILTER (
    WHERE ABS(p.paid_total - i.expected_total) > 0.01
) > 0
ORDER BY COUNT(*) FILTER (
    WHERE ABS(p.paid_total - i.expected_total) > 0.01
) DESC;

-- Measure reconciliation coverage and discrepancy size across all orders.
WITH items AS (
    SELECT
        order_id,
        SUM(price::numeric + freight_value::numeric) AS expected_total
    FROM raw.order_items
    GROUP BY order_id
),
payments AS (
    SELECT
        order_id,
        COUNT(*) AS payment_count,
        SUM(payment_value::numeric) AS paid_total
    FROM raw.order_payments
    GROUP BY order_id
),
audit AS (
    SELECT
        o.order_id,
        i.order_id IS NOT NULL AS has_items,
        p.order_id IS NOT NULL AS has_payments,
        p.payment_count,
        p.paid_total - i.expected_total AS difference
    FROM raw.orders o
    LEFT JOIN items i ON o.order_id = i.order_id
    LEFT JOIN payments p ON o.order_id = p.order_id
)
SELECT
    COUNT(*) FILTER (
        WHERE has_items AND has_payments
    ) AS comparable_orders,
    COUNT(*) FILTER (
        WHERE ABS(difference) > 0.01
    ) AS flagged_orders,
    COUNT(*) FILTER (
        WHERE ABS(difference) > 0.01 AND payment_count > 1
    ) AS flagged_with_multiple_payments,
    COUNT(*) FILTER (
        WHERE difference > 0.01
    ) AS payments_above,
    COUNT(*) FILTER (
        WHERE difference < -0.01
    ) AS payments_below,
    ROUND(SUM(ABS(difference)) FILTER (
        WHERE ABS(difference) > 0.01
    ), 2) AS total_absolute_difference,
    ROUND(MAX(ABS(difference)), 2) AS largest_difference
FROM audit;

-- Check recorded event sequences without changing source values.
WITH dates AS (
    SELECT
        order_status,
        order_purchase_timestamp::timestamp AS purchased_at,
        order_approved_at::timestamp AS approved_at,
        order_delivered_carrier_date::timestamp AS carrier_at,
        order_delivered_customer_date::timestamp AS delivered_at,
        order_estimated_delivery_date::timestamp AS estimated_at
    FROM raw.orders
)
SELECT
    COUNT(*) FILTER (
        WHERE approved_at < purchased_at
    ) AS approval_before_purchase,
    COUNT(*) FILTER (
        WHERE carrier_at < purchased_at
    ) AS carrier_before_purchase,
    COUNT(*) FILTER (
        WHERE carrier_at < approved_at
    ) AS carrier_before_approval,
    COUNT(*) FILTER (
        WHERE delivered_at < carrier_at
    ) AS delivery_before_carrier,
    COUNT(*) FILTER (
        WHERE estimated_at::date < purchased_at::date
    ) AS estimated_date_before_purchase,
    COUNT(*) FILTER (
        WHERE order_status <> 'delivered'
          AND delivered_at IS NOT NULL
    ) AS other_status_with_delivery_date
FROM dates;

-- Check whether multiple reviews contain different scores.
WITH review_groups AS (
    SELECT
        order_id,
        COUNT(*) AS review_count,
        COUNT(DISTINCT review_id) AS distinct_review_ids,
        COUNT(DISTINCT review_score::integer) AS distinct_scores
    FROM raw.order_reviews
    GROUP BY order_id
)
SELECT
    COUNT(*) FILTER (
        WHERE review_count > 1
    ) AS orders_with_multiple_reviews,
    COUNT(*) FILTER (
        WHERE review_count > 1 AND distinct_scores > 1
    ) AS multiple_reviews_with_different_scores,
    COUNT(*) FILTER (
        WHERE review_count > distinct_review_ids
    ) AS orders_with_repeated_review_id,
    MAX(review_count) AS most_reviews_for_one_order
FROM review_groups;

-- Measure repeat purchasing among customers with delivered orders.
WITH customer_orders AS (
    SELECT
        c.customer_unique_id,
        COUNT(*) AS delivered_orders
    FROM raw.orders o
    JOIN raw.customers c ON o.customer_id = c.customer_id
    WHERE o.order_status = 'delivered'
    GROUP BY c.customer_unique_id
)
SELECT
    COUNT(*) AS customers_with_delivered_orders,
    COUNT(*) FILTER (
        WHERE delivered_orders > 1
    ) AS repeat_customers,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE delivered_orders > 1)
        / NULLIF(COUNT(*), 0),
        2
    ) AS repeat_customer_pct,
    MAX(delivered_orders) AS most_orders_per_customer
FROM customer_orders;

-- Check monetary values and review-score ranges.
SELECT
    'order_items' AS source_table,
    COUNT(*) FILTER (
        WHERE price IS NULL OR freight_value IS NULL
    ) AS missing_required_values,
    COUNT(*) FILTER (
        WHERE price::numeric < 0 OR freight_value::numeric < 0
    ) AS negative_amount_rows,
    COUNT(*) FILTER (
        WHERE price::numeric = 0
    ) AS zero_value_rows
FROM raw.order_items

UNION ALL

SELECT
    'order_payments',
    COUNT(*) FILTER (
        WHERE payment_value IS NULL
    ),
    COUNT(*) FILTER (
        WHERE payment_value::numeric < 0
    ),
    COUNT(*) FILTER (
        WHERE payment_value::numeric = 0
    )
FROM raw.order_payments;

-- Check that ratings fall within the expected 1–5 range.
SELECT
    COUNT(*) FILTER (
        WHERE review_score IS NULL
    ) AS missing_scores,
    COUNT(*) FILTER (
        WHERE review_score::integer NOT BETWEEN 1 AND 5
    ) AS scores_outside_range,
    MIN(review_score::integer) AS lowest_score,
    MAX(review_score::integer) AS highest_score
FROM raw.order_reviews;

-- Inspect zero payment entries alongside each order's total payments.
WITH payment_totals AS (
    SELECT
        order_id,
        COUNT(*) AS payment_count,
        SUM(payment_value::numeric) AS total_paid
    FROM raw.order_payments
    GROUP BY order_id
)
SELECT
    p.order_id,
    o.order_status,
    p.payment_sequential,
    p.payment_type,
    p.payment_installments,
    t.payment_count,
    t.total_paid
FROM raw.order_payments p
JOIN payment_totals t ON p.order_id = t.order_id
JOIN raw.orders o ON p.order_id = o.order_id
WHERE p.payment_value::numeric = 0
ORDER BY p.order_id, p.payment_sequential::integer;