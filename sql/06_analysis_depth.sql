-- Run as database owner (aman) in DBeaver, once, after scripts 01-05.
-- Source tables are preserved. Expose only these reporting views to the reader.
BEGIN;
CREATE OR REPLACE VIEW analytics.category_monthly AS
SELECT CAST(DATE_TRUNC('month', CAST(o.order_purchase_timestamp AS TIMESTAMP)) AS DATE) AS purchase_month,
       p.category_label,
       COUNT(*) AS items_sold,
       COUNT(DISTINCT i.order_id) AS orders_containing_category,
       SUM(CAST(i.price AS NUMERIC(18,2))) AS merchandise_value
FROM raw.order_items i
JOIN raw.orders o ON o.order_id = i.order_id
JOIN staging.products p ON p.product_id = i.product_id
WHERE o.order_status = 'delivered'
  AND CAST(o.order_purchase_timestamp AS TIMESTAMP) >= TIMESTAMP '2017-01-01'
  AND CAST(o.order_purchase_timestamp AS TIMESTAMP) < TIMESTAMP '2018-09-01'
GROUP BY 1, 2;

CREATE OR REPLACE VIEW analytics.seller_monthly AS
SELECT CAST(DATE_TRUNC('month', CAST(o.order_purchase_timestamp AS TIMESTAMP)) AS DATE) AS purchase_month,
       i.seller_id,
       COUNT(*) AS items_sold,
       COUNT(DISTINCT i.order_id) AS orders_containing_seller,
       SUM(CAST(i.price AS NUMERIC(18,2))) AS merchandise_value
FROM raw.order_items i
JOIN raw.orders o ON o.order_id = i.order_id
WHERE o.order_status = 'delivered'
  AND CAST(o.order_purchase_timestamp AS TIMESTAMP) >= TIMESTAMP '2017-01-01'
  AND CAST(o.order_purchase_timestamp AS TIMESTAMP) < TIMESTAMP '2018-09-01'
GROUP BY 1, 2;

CREATE OR REPLACE VIEW analytics.state_delivery_monthly AS
WITH order_flags AS (
 SELECT CAST(DATE_TRUNC('month', CAST(o.order_purchase_timestamp AS TIMESTAMP)) AS DATE) AS purchase_month,
        c.customer_state,
        CASE WHEN o.order_purchase_timestamp IS NOT NULL
              AND o.order_delivered_customer_date IS NOT NULL
              AND o.order_estimated_delivery_date IS NOT NULL
              AND CAST(o.order_delivered_customer_date AS TIMESTAMP) >= CAST(o.order_purchase_timestamp AS TIMESTAMP)
             THEN 1 ELSE 0 END AS assessable,
        CASE WHEN CAST(o.order_delivered_customer_date AS DATE) > CAST(o.order_estimated_delivery_date AS DATE)
             THEN 1 ELSE 0 END AS after_estimate
 FROM raw.orders o
 JOIN raw.customers c ON c.customer_id = o.customer_id
 WHERE o.order_status = 'delivered'
   AND CAST(o.order_purchase_timestamp AS TIMESTAMP) >= TIMESTAMP '2017-01-01'
   AND CAST(o.order_purchase_timestamp AS TIMESTAMP) < TIMESTAMP '2018-09-01'
)
SELECT purchase_month, customer_state, COUNT(*) AS delivered_orders,
       SUM(assessable) AS assessable_delivery_orders,
       SUM(CASE WHEN assessable = 1 AND after_estimate = 1 THEN 1 ELSE 0 END) AS late_orders
FROM order_flags GROUP BY 1, 2;

GRANT SELECT ON analytics.category_monthly, analytics.seller_monthly,
                analytics.state_delivery_monthly TO causyn_reader;
COMMIT;
