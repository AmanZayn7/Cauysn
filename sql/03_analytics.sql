CREATE SCHEMA IF NOT EXISTS analytics;

CREATE OR REPLACE VIEW analytics.orders AS
WITH combined AS (
    SELECT
        o.*,
        c.customer_unique_id,
        c.customer_city,
        c.customer_state,

        COALESCE(i.item_count, 0) AS item_count,
        COALESCE(i.seller_count, 0) AS seller_count,
        i.merchandise_value,
        i.freight_value,
        i.items_plus_freight,

        COALESCE(p.payment_count, 0) AS payment_count,
        p.recorded_payment_value,

        COALESCE(r.review_count, 0) AS review_count,
        r.average_review_score,
        COALESCE(r.conflicting_review_scores, FALSE)
            AS conflicting_review_scores,

        i.order_id IS NULL AS missing_items,
        p.order_id IS NULL AS missing_payments,

        p.recorded_payment_value - i.items_plus_freight
            AS payment_difference

    FROM staging.orders o
    LEFT JOIN staging.customers c
        ON o.customer_id = c.customer_id
    LEFT JOIN staging.order_item_summary i
        ON o.order_id = i.order_id
    LEFT JOIN staging.order_payment_summary p
        ON o.order_id = p.order_id
    LEFT JOIN staging.order_review_summary r
        ON o.order_id = r.order_id
)
SELECT
    *,
    -- NULL means reconciliation cannot be assessed.
    ABS(payment_difference) > 0.01 AS payment_discrepancy,

    CASE
        WHEN valid_purchase_to_delivery
        THEN EXTRACT(EPOCH FROM (delivered_at - purchased_at))
             / 86400.0
    END AS purchase_to_delivery_days,

    -- Compare calendar dates because the estimate is a date deadline.
    CASE
        WHEN valid_purchase_to_delivery
             AND estimated_at IS NOT NULL
        THEN delivered_at::date > estimated_at::date
    END AS is_late_delivery

FROM combined;

SELECT
    COUNT(*) AS total_rows,
    COUNT(DISTINCT order_id) AS unique_orders,
    COUNT(*) FILTER (WHERE missing_items) AS missing_items,
    COUNT(*) FILTER (WHERE missing_payments) AS missing_payments,
    COUNT(*) FILTER (WHERE payment_discrepancy) AS discrepancies,
    COUNT(*) FILTER (
        WHERE valid_purchase_to_delivery
    ) AS eligible_delivery_orders
FROM analytics.orders;

-- Confirm that combining tables did not inflate monetary totals.
SELECT
    SUM(merchandise_value)
        - (
            SELECT SUM(merchandise_value)
            FROM staging.order_items
        ) AS merchandise_difference,

    SUM(freight_value)
        - (
            SELECT SUM(freight_value)
            FROM staging.order_items
        ) AS freight_difference,

    SUM(recorded_payment_value)
        - (
            SELECT SUM(payment_value)
            FROM staging.order_payments
        ) AS payment_difference

FROM analytics.orders;

-- Baseline metrics for delivered orders purchased in our analysis window.
WITH reporting_orders AS (
    SELECT *
    FROM analytics.orders
    WHERE purchased_at >= TIMESTAMP '2017-01-01'
      AND purchased_at <  TIMESTAMP '2018-09-01'
      AND is_delivered
)
SELECT
    COUNT(*) AS delivered_orders,

    ROUND(SUM(merchandise_value), 2)
        AS delivered_merchandise_value,

    ROUND(
        SUM(merchandise_value)
        / NULLIF(COUNT(*) FILTER (
            WHERE merchandise_value IS NOT NULL
        ), 0),
        2
    ) AS average_merchandise_value_per_order,

    COUNT(*) FILTER (
        WHERE is_late_delivery IS NOT NULL
    ) AS orders_with_assessable_delivery,

    COUNT(*) FILTER (
        WHERE is_late_delivery
    ) AS late_orders,

    ROUND(
        100.0 * COUNT(*) FILTER (WHERE is_late_delivery)
        / NULLIF(COUNT(*) FILTER (
            WHERE is_late_delivery IS NOT NULL
        ), 0),
        2
    ) AS late_delivery_pct

FROM reporting_orders;

-- Monthly metrics grouped by purchase month.
CREATE OR REPLACE VIEW analytics.monthly_performance AS
SELECT
    DATE_TRUNC('month', purchased_at)::date AS purchase_month,
    COUNT(*) AS delivered_orders,
    SUM(merchandise_value) AS delivered_merchandise_value,

    SUM(merchandise_value)
        / NULLIF(COUNT(*) FILTER (
            WHERE merchandise_value IS NOT NULL
        ), 0) AS average_merchandise_value_per_order,

    COUNT(*) FILTER (
        WHERE is_late_delivery IS NOT NULL
    ) AS assessable_delivery_orders,

    COUNT(*) FILTER (
        WHERE is_late_delivery
    ) AS late_orders,

    100.0 * COUNT(*) FILTER (WHERE is_late_delivery)
        / NULLIF(COUNT(*) FILTER (
            WHERE is_late_delivery IS NOT NULL
        ), 0) AS late_delivery_pct

FROM analytics.orders
WHERE is_delivered
  AND purchased_at >= TIMESTAMP '2017-01-01'
  AND purchased_at <  TIMESTAMP '2018-09-01'
GROUP BY DATE_TRUNC('month', purchased_at)::date;

SELECT
    COUNT(*) AS months,
    SUM(delivered_orders) AS delivered_orders,
    ROUND(SUM(delivered_merchandise_value), 2)
        AS delivered_merchandise_value,
    SUM(assessable_delivery_orders) AS assessable_delivery_orders,
    SUM(late_orders) AS late_orders
FROM analytics.monthly_performance;

-- Compare merchandise value with the previous purchase month.
WITH monthly AS (
    SELECT
        *,
        LAG(delivered_merchandise_value) OVER (
            ORDER BY purchase_month
        ) AS previous_month_value
    FROM analytics.monthly_performance
)
SELECT
    purchase_month,
    delivered_orders,
    ROUND(delivered_merchandise_value, 2) AS merchandise_value,
    ROUND(previous_month_value, 2) AS previous_month_value,
    ROUND(
        delivered_merchandise_value - previous_month_value,
        2
    ) AS change_value,
    ROUND(
        100.0 * (
            delivered_merchandise_value - previous_month_value
        ) / NULLIF(previous_month_value, 0),
        2
    ) AS change_pct,
    ROUND(late_delivery_pct, 2) AS late_delivery_pct
FROM monthly
ORDER BY purchase_month;

-- Decompose the December 2017 decline by product category.
WITH category_totals AS (
    SELECT
        p.category_label,

        SUM(CASE
            WHEN o.purchased_at < TIMESTAMP '2017-12-01'
            THEN i.merchandise_value ELSE 0
        END) AS november_value,

        SUM(CASE
            WHEN o.purchased_at >= TIMESTAMP '2017-12-01'
            THEN i.merchandise_value ELSE 0
        END) AS december_value

    FROM staging.order_items i
    JOIN staging.orders o ON i.order_id = o.order_id
    JOIN staging.products p ON i.product_id = p.product_id
    WHERE o.is_delivered
      AND o.purchased_at >= TIMESTAMP '2017-11-01'
      AND o.purchased_at <  TIMESTAMP '2018-01-01'
    GROUP BY p.category_label
),
changes AS (
    SELECT
        *,
        december_value - november_value AS change_value
    FROM category_totals
)
SELECT
    category_label,
    ROUND(november_value, 2) AS november_value,
    ROUND(december_value, 2) AS december_value,
    ROUND(change_value, 2) AS change_value,
    ROUND(
        SUM(change_value) OVER (),
        2
    ) AS overall_change
FROM changes
ORDER BY change_value;

-- Compare item counts and average item values for the top contributors.
SELECT
    p.category_label,
    DATE_TRUNC('month', o.purchased_at)::date AS purchase_month,
    COUNT(*) AS items_sold,
    COUNT(DISTINCT o.order_id) AS orders_containing_category,
    ROUND(SUM(i.merchandise_value), 2) AS merchandise_value,
    ROUND(AVG(i.merchandise_value), 2) AS average_item_value
FROM staging.order_items i
JOIN staging.orders o ON i.order_id = o.order_id
JOIN staging.products p ON i.product_id = p.product_id
WHERE o.is_delivered
  AND o.purchased_at >= TIMESTAMP '2017-11-01'
  AND o.purchased_at <  TIMESTAMP '2018-01-01'
  AND p.category_label IN (
      'bed_bath_table',
      'computers_accessories',
      'furniture_decor'
  )
GROUP BY
    p.category_label,
    DATE_TRUNC('month', o.purchased_at)::date
ORDER BY category_label, purchase_month;