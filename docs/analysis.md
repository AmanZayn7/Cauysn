# Reporting analyses

Causyn supports monthly trends, category rankings, seller rankings and delivery performance by customer state. These analyses use approved reporting tools; forecasting, external data retrieval and arbitrary SQL are outside their scope.

## Reporting views and checks

From the repository root, with the project environment active and the local PostgreSQL database configured:

```bash
python install_analysis_depth.py --user YOUR_LOCAL_OWNER
python evaluate_depth.py --self-test
python evaluate_depth.py --database
python evaluate.py
```

The installer applies `sql/06_analysis_depth.sql`, creates three reporting views and grants SELECT to `causyn_reader`. It preserves raw/staging data. The SQL can also be applied directly by a database administrator. Application agents do not invoke the installer or write to the business tables.

Database-backed checks make no Gemini requests. They verify the baseline of 96,211 delivered orders, BRL 13,181,027.13 merchandise value, 96,203 assessable deliveries and 6,531 late orders, and generate four local HTML charts.

## Analyses and charts

| Analysis | Tool | Chart |
| --- | --- | --- |
| Monthly performance | `get_monthly_trend` | Merchandise trend line |
| Categories by delivered merchandise value | `get_category_performance` | Horizontal ranking bars |
| Sellers by delivered merchandise value | `get_seller_performance` | Horizontal ranking bars |
| Delivery by customer destination state | `get_state_delivery` | Late-rate comparison bars |

All range tools use inclusive `start_month` and `end_month`, within January 2017–August 2018. A single-month query uses identical endpoints. Merchandise value is in BRL, excludes freight and is not profit or audited corporate revenue.

Example: “Rank categories by delivered merchandise value for 2017-11 through 2017-12.”

## Interpretation and verification

Category and seller rankings return the leading ten groups plus omitted totals for reconciliation. Items sold counts item records. Distinct-order counts can overlap between categories or sellers and cannot be added into a unique-order total. Average item value divides merchandise value by item count.

Seller IDs are anonymized identifiers. States identify customer destinations. Late delivery compares calendar dates, with a denominator restricted to assessable deliveries. Missing coverage produces a null rate. State charts omit groups with fewer than 30 assessable orders; evidence retains all states. This is a display threshold, not a statistical significance test.

Structured claims identify the range, group, metric, unit and evidence index. Checks cover averages, rates, chronology, ranking and partition reconciliation. Explicit visualization-agent charts are checked against verified evidence. Inferred interface charts display tool data but do not receive that same artifact-mapping check. AI review cannot override failed deterministic checks. Trends and rankings do not establish causes.

Independent development validation used DuckDB against the project Olist CSVs for twelve analysis/range combinations. DuckDB is not an application dependency. Separate PostgreSQL checks are required for its execution and grants; offline fixtures do not establish live Gemini behavior or browser rendering.

## Live evaluation

```bash
python evaluate_depth.py --live --case trend
python evaluate_depth.py --live --case categories
python evaluate_depth.py --live --case sellers
python evaluate_depth.py --live --case states
```

These commands use Gemini and may incur charges. Results are stored under `evaluations/results/depth_*.json`. Model planning and review remain fallible; automated checks do not establish every statement's correctness.
