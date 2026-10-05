-- Validation checks for the current Olist snapshot.
WITH checks AS (
    SELECT
        'Analytics preserves all orders' AS check_name,
        (SELECT COUNT(*) FROM analytics.orders)
            = (SELECT COUNT(*) FROM raw.orders) AS passed

    UNION ALL

    SELECT
        'One analytics row per order',
        COUNT(*) = COUNT(DISTINCT order_id)
    FROM analytics.orders

    UNION ALL

    SELECT
        'Merchandise totals preserved',
        (SELECT SUM(merchandise_value) FROM analytics.orders)
            = (SELECT SUM(price::numeric) FROM raw.order_items)

    UNION ALL

    SELECT
        'Freight totals preserved',
        (SELECT SUM(freight_value) FROM analytics.orders)
            = (SELECT SUM(freight_value::numeric) FROM raw.order_items)

    UNION ALL

    SELECT
        'Payment totals preserved',
        (SELECT SUM(recorded_payment_value) FROM analytics.orders)
            = (SELECT SUM(payment_value::numeric)
               FROM raw.order_payments)

    UNION ALL

    SELECT
        'Review composite keys are unique',
        NOT EXISTS (
            SELECT 1
            FROM staging.order_reviews
            GROUP BY order_id, review_id
            HAVING COUNT(*) > 1
        )

    UNION ALL

    SELECT
        'Payment discrepancies match audit: 303',
        COUNT(*) = 303
    FROM analytics.orders
    WHERE payment_discrepancy

    UNION ALL

    SELECT
        'Eligible delivery orders match audit: 96470',
        COUNT(*) = 96470
    FROM analytics.orders
    WHERE valid_purchase_to_delivery

    UNION ALL

    SELECT
        'Monthly delivered orders match baseline: 96211',
        SUM(delivered_orders) = 96211
    FROM analytics.monthly_performance

    UNION ALL

    SELECT
        'Monthly merchandise matches baseline: 13181027.13',
        SUM(delivered_merchandise_value) = 13181027.13
    FROM analytics.monthly_performance

    UNION ALL

    SELECT
        'Monthly delivery coverage matches baseline: 96203',
        SUM(assessable_delivery_orders) = 96203
    FROM analytics.monthly_performance

    UNION ALL

    SELECT
        'Monthly late orders match baseline: 6531',
        SUM(late_orders) = 6531
    FROM analytics.monthly_performance
)
SELECT
    check_name,
    CASE
        WHEN passed THEN 'PASS'
        ELSE 'FAIL'
    END AS result
FROM checks
ORDER BY check_name;