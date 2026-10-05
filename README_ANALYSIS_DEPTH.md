# CAUSYN — SQL depth and visualization update

This is the final agreed analytical expansion before deployment: monthly trends,
category performance, seller performance, and delivery performance by customer
state. No forecasting, external data sources, or arbitrary SQL are introduced.

## Install on your Mac

Download `causyn_analysis_update.zip` into Downloads. Stop the running web server
with Control+C, then run:

```bash
unzip -o ~/Downloads/causyn_analysis_update.zip -d ~/Desktop/causyn
cd ~/Desktop/causyn
./.venv/bin/python install_analysis_depth.py --user aman
./.venv/bin/python evaluate_depth.py --self-test
./.venv/bin/python evaluate_depth.py --database
./.venv/bin/python evaluate.py
```

The installer uses your local database owner connection to run
`sql/06_analysis_depth.sql`. It creates three reporting views, grants only SELECT
on those views to `causyn_reader`, and preserves existing raw/staging data.
You can alternatively open and execute the SQL script in DBeaver as the owner.
The agents never invoke the installer or write to the database. No new Python
package is required for these application features.

The database check makes no Gemini requests. It verifies the established
full-period baseline (96,211 orders; BRL 13,181,027.13 merchandise; 96,203
assessable delivery orders; 6,531 late orders), validates each range result, and
saves four local HTML charts. Do not proceed to live checks if it fails.

## One live check at a time

```bash
./.venv/bin/python evaluate_depth.py --live --case trend
./.venv/bin/python evaluate_depth.py --live --case categories
./.venv/bin/python evaluate_depth.py --live --case sellers
./.venv/bin/python evaluate_depth.py --live --case states
```

Each command makes paid Gemini requests and uses the existing request and review
limits. Run one first, inspect its answer and report, then proceed with the other
cases. Automated PASS is not proof of correctness; model planning and review are
fallible. Reports are saved under `evaluations/results/depth_*.json`.

Restart with `./.venv/bin/python web_app.py`, and hard-refresh your browser with
Command+Shift+R. New capabilities operate in Live mode. The three existing Demo
examples remain recorded examples; they do not simulate fresh database queries.

## Approved analyses and chart types

| Question | SQL tool | Explicit chart |
|---|---|---|
| Monthly performance across an inclusive range | `get_monthly_trend` | Merchandise trend line |
| Leading categories by delivered merchandise value | `get_category_performance` | Horizontal ranking bars |
| Leading sellers by delivered merchandise value | `get_seller_performance` | Horizontal ranking bars |
| Delivery by customer destination state | `get_state_delivery` | Late-rate comparison bars |

Example questions:

- “Show a monthly merchandise value trend from 2017-01 through 2018-08.”
- “Rank categories by delivered merchandise value for 2017-11 through 2017-12.”
- “Chart the leading sellers by delivered merchandise value for 2018-03.”
- “Chart late-delivery rates by customer state for 2018-03.”

All range tools use inclusive `start_month` and `end_month`. A single-month
question uses identical endpoints. Supported months remain 2017-01–2018-08.
Money is BRL; merchandise excludes freight and is not profit or corporate revenue.

## Metric interpretation

- Category/seller values sum item merchandise. No join to payments or reviews
  can multiply those values. Rankings return the leading 10 groups plus omitted
  group totals for reconciliation against the established monthly view.
- Items sold counts item records. Group order counts are distinct within each
  category or seller. An order can appear in several groups; these counts must
  not be added. Average item value divides merchandise by item count, not orders.
- Seller IDs are anonymized identifiers. They are not business names.
- States are customer destinations, not seller locations. Each order contributes
  once. Delivery is assessable only with purchase, actual delivery and estimated
  delivery timestamps, and actual delivery at or after purchase.
- Late delivery compares calendar dates. The denominator contains only
  assessable delivered orders. A missing denominator produces null, never a
  fabricated zero rate. State charts omit groups with fewer than 30 assessable
  orders; evidence retains all states. This threshold is a display safeguard,
  not a statistical significance test.
- Differences, rankings and trends do not prove causes or seller responsibility.

## Verification

Structured claims must identify the inclusive range, exact group identifier,
metric, unit and evidence index. Evidence checks recompute available averages,
rates, count bounds, chronology, ranking order, and partition reconciliation.
Explicit chart specifications are rebuilt from verified source evidence and
compared exactly. The final AI reviewer remains mandatory and cannot override
failed local checks. Inferred UI charts for ordinary SQL answers are presentation
of tool data; only an explicit visualization-agent artifact gets chart mapping
verification. Full reviewed answers and raw evidence remain accessible.

## Validation completed before delivery

- Twelve analyses/range combinations ran against the actual uploaded Olist CSVs
  using DuckDB as an independent SQL engine; totals matched established baselines.
- Eleven new contract/claim/chart tests passed, including duplicate groups,
  invalid periods, zero coverage, ranking partitions and tampered values.
- Existing SQL, numerical verification, visualization and delegation regression
  checks passed, along with new mocked orchestration checks for all four analyses.
- Interface logic checks covered all four range charts, exact plotted values,
  state coverage notes, and export units; existing interface/server tests passed.

PostgreSQL-specific execution/grants and real Gemini planning still require the
Mac commands above. Actual browser rendering must be checked on the Mac as well.
DuckDB is used only for independent development validation, not the application.
