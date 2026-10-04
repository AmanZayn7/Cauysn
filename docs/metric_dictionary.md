# CAUSYN Metric Dictionary

## Default reporting scope
- Purchase dates: January 1, 2017 through August 31, 2018.
- Include orders whose recorded status is delivered.
- Currency: Brazilian real (BRL).
- This is historical marketplace data, not a live business feed.

## Delivered merchandise value
Sum of item prices for eligible orders.
Excludes freight charges.
Does not represent profit or Olist's corporate revenue.

## Delivered order count
Number of distinct eligible order IDs.

## Average merchandise value per order
Delivered merchandise value divided by eligible orders
with a known merchandise value.

## Late delivery
Actual customer delivery calendar date is later than
the estimated delivery calendar date.

## Late-delivery rate
Late orders divided by orders with assessable delivery,
multiplied by 100.
Assessable orders are delivered, have purchase and delivery
timestamps, have delivery at or after purchase, and have
an estimated delivery date.

## Purchase-to-delivery duration
Elapsed seconds between purchase and customer delivery,
divided by 86,400.
Only calculated for valid_purchase_to_delivery orders.

## Payment reconciliation
Recorded payments minus item prices plus freight:
payment_difference = recorded_payment_value
                   - (merchandise_value + freight_value).
Flag absolute differences greater than 0.01 BRL.
Missing records mean reconciliation is unknown, not zero.
Differences are unexplained, not assumed losses or fees.

## Customer identity and repeat purchasing
Use customer_unique_id to identify repeat customers.
customer_id links orders to customer records.
Repeat purchasing describes only the observed dataset;
it does not establish churn or lifetime retention.

## Review handling
Preserve every review.
Use (order_id, review_id) as the composite identifier.
Order-level average score weights each review equally.
Flag orders whose reviews have different scores.
Blank comments are not neutral sentiment.

## Interpretation rules
Category contributions explain where a change occurred.
Item counts and average item values explain its arithmetic.
Neither establishes a causal explanation.
Average item value can change because product mix changes.