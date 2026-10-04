-- Staging views reflect the raw data without deleting source records.
CREATE SCHEMA IF NOT EXISTS staging;

-- One row per order, with typed timestamps and quality flags.
CREATE OR REPLACE VIEW staging.orders AS
WITH typed AS (
    SELECT
        order_id,
        customer_id,
        order_status,
        order_purchase_timestamp::timestamp AS purchased_at,
        order_approved_at::timestamp AS approved_at,
        order_delivered_carrier_date::timestamp AS carrier_at,
        order_delivered_customer_date::timestamp AS delivered_at,
        order_estimated_delivery_date::timestamp AS estimated_at
    FROM raw.orders
)
SELECT
    *,
    order_status = 'delivered' AS is_delivered,

    order_status = 'delivered'
        AND delivered_at IS NULL
        AS missing_delivered_timestamp,

    COALESCE(carrier_at < purchased_at, FALSE)
        AS carrier_before_purchase,

    COALESCE(carrier_at < approved_at, FALSE)
        AS carrier_before_approval,

    COALESCE(delivered_at < carrier_at, FALSE)
        AS delivery_before_carrier,

    order_status <> 'delivered'
        AND delivered_at IS NOT NULL
        AS other_status_with_delivery_date,

    -- Eligibility for purchase-to-customer delivery duration.
    (
        order_status = 'delivered'
        AND purchased_at IS NOT NULL
        AND delivered_at IS NOT NULL
        AND delivered_at >= purchased_at
    ) AS valid_purchase_to_delivery

FROM typed;


-- Confirm row preservation and delivery flags.
SELECT
    COUNT(*) AS total_orders,
    COUNT(*) FILTER (
        WHERE missing_delivered_timestamp
    ) AS delivered_missing_date,
    COUNT(*) FILTER (
        WHERE valid_purchase_to_delivery
    ) AS eligible_for_delivery_duration
FROM staging.orders;

-- One row per order item. Preserve every source record.
CREATE OR REPLACE VIEW staging.order_items AS
SELECT
    order_id,
    order_item_id::integer AS order_item_id,
    product_id,
    seller_id,
    shipping_limit_date::timestamp AS shipping_limit_at,
    price::numeric AS merchandise_value,
    freight_value::numeric AS freight_value
FROM raw.order_items;

-- One row per payment entry, including zero-value entries.
CREATE OR REPLACE VIEW staging.order_payments AS
SELECT
    order_id,
    payment_sequential::integer AS payment_sequential,
    payment_type,
    payment_installments::integer AS payment_installments,
    payment_value::numeric AS payment_value,
    payment_value::numeric = 0 AS is_zero_payment
FROM raw.order_payments;

-- Verify that staging preserves rows and monetary totals.
SELECT
    'order_items' AS table_name,
    (SELECT COUNT(*) FROM raw.order_items) AS raw_rows,
    COUNT(*) AS staging_rows,
    SUM(merchandise_value)
        - (SELECT SUM(price::numeric) FROM raw.order_items)
        AS amount_difference
FROM staging.order_items

UNION ALL

SELECT
    'order_payments',
    (SELECT COUNT(*) FROM raw.order_payments),
    COUNT(*),
    SUM(payment_value)
        - (SELECT SUM(payment_value::numeric) FROM raw.order_payments)
FROM staging.order_payments;

-- Preserve both customer identifiers and ZIP prefixes as text.
CREATE OR REPLACE VIEW staging.customers AS
SELECT
    customer_id,
    customer_unique_id,
    customer_zip_code_prefix,
    customer_city,
    customer_state
FROM raw.customers;

-- Preserve original categories and expose translation coverage.
CREATE OR REPLACE VIEW staging.products AS
SELECT
    p.product_id,
    p.product_category_name AS category_original,
    t.product_category_name_english AS category_english,

    COALESCE(
        t.product_category_name_english,
        p.product_category_name,
        'Unknown'
    ) AS category_label,

    p.product_category_name IS NULL AS missing_category,

    p.product_category_name IS NOT NULL
        AND t.product_category_name IS NULL
        AS missing_translation,

    p.product_weight_g::numeric AS weight_g,
    p.product_length_cm::numeric AS length_cm,
    p.product_height_cm::numeric AS height_cm,
    p.product_width_cm::numeric AS width_cm,

    p.product_name_lenght::integer AS product_name_length,
    p.product_description_lenght::integer AS product_description_length,
    p.product_photos_qty::integer AS product_photos_qty,

    COALESCE(p.product_weight_g::numeric = 0, FALSE)
        AS zero_recorded_weight

FROM raw.products p
LEFT JOIN raw.category_translations t
    ON p.product_category_name = t.product_category_name;

SELECT
    (SELECT COUNT(*) FROM staging.customers) AS customer_rows,
    COUNT(*) AS product_rows,
    COUNT(*) FILTER (WHERE missing_category) AS missing_categories,
    COUNT(*) FILTER (WHERE missing_translation) AS missing_translations,
    COUNT(*) FILTER (WHERE zero_recorded_weight) AS zero_weights
FROM staging.products;

CREATE OR REPLACE VIEW staging.sellers AS
SELECT
    seller_id,
    seller_zip_code_prefix,
    seller_city,
    seller_state
FROM raw.sellers;

-- Keep every review; (order_id, review_id) identifies each record.
CREATE OR REPLACE VIEW staging.order_reviews AS
SELECT
    order_id,
    review_id,
    review_score::integer AS review_score,
    review_comment_title,
    review_comment_message,
    review_creation_date::timestamp AS review_created_at,
    review_answer_timestamp::timestamp AS review_answered_at,

    NULLIF(BTRIM(review_comment_message), '') IS NOT NULL
        AS has_comment_text

FROM raw.order_reviews;

SELECT
    (SELECT COUNT(*) FROM staging.sellers) AS seller_rows,
    COUNT(*) AS review_rows,
    COUNT(*) FILTER (WHERE has_comment_text) AS reviews_with_text,
    (
        SELECT COUNT(*)
        FROM (
            SELECT order_id, review_id
            FROM staging.order_reviews
            GROUP BY order_id, review_id
            HAVING COUNT(*) > 1
        ) duplicates
    ) AS duplicate_review_keys
FROM staging.order_reviews;

-- One row per order that has items.
CREATE OR REPLACE VIEW staging.order_item_summary AS
SELECT
    order_id,
    COUNT(*) AS item_count,
    COUNT(DISTINCT seller_id) AS seller_count,
    SUM(merchandise_value) AS merchandise_value,
    SUM(freight_value) AS freight_value,
    SUM(merchandise_value + freight_value) AS items_plus_freight
FROM staging.order_items
GROUP BY order_id;

-- One row per order that has payment records.
CREATE OR REPLACE VIEW staging.order_payment_summary AS
SELECT
    order_id,
    COUNT(*) AS payment_count,
    SUM(payment_value) AS recorded_payment_value,
    COUNT(*) FILTER (WHERE is_zero_payment) AS zero_payment_entries
FROM staging.order_payments
GROUP BY order_id;

-- One row per reviewed order, preserving disagreement.
CREATE OR REPLACE VIEW staging.order_review_summary AS
SELECT
    order_id,
    COUNT(*) AS review_count,
    AVG(review_score) AS average_review_score,
    COUNT(DISTINCT review_score) > 1 AS conflicting_review_scores,
    COUNT(*) FILTER (WHERE has_comment_text) AS comments_with_text
FROM staging.order_reviews
GROUP BY order_id;

SELECT
    (
        SELECT SUM(item_count)
        FROM staging.order_item_summary
    ) AS preserved_items,
    (
        SELECT SUM(payment_count)
        FROM staging.order_payment_summary
    ) AS preserved_payments,
    (
        SELECT SUM(review_count)
        FROM staging.order_review_summary
    ) AS preserved_reviews,
    (
        SELECT COUNT(*)
        FROM staging.order_review_summary
        WHERE conflicting_review_scores
    ) AS orders_with_conflicting_scores;