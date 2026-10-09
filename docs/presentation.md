# Findings, charts and result labels

The presentation layer summarizes retrieved evidence while retaining the complete reviewed answer and detailed verification results.

## Summaries and charts

- Monthly trends lead with the selected range's merchandise total and unique delivered-order count, then identify the highest-value month. Ties are disclosed; the summary does not assume a steady decline.
- Category comparisons show up to three negative and three positive contributions in a diverging chart. Labels, exact plotted values, SVG/CSV exports and omitted-category notes remain visible. Tool-backed contributions appear before answer checks and AI review.
- Trend, comparison and waterfall axes use round 1/2/2.5/5/10 steps and consistent k/M suffixes. Source values and exports retain full precision.
- Display category names use sentence case. Raw identifiers remain intact in evidence, chart specifications and CSV exports.
- New saved HTML reports use the dark purple theme and a Back to Causyn link. Existing saved reports retain their earlier presentation.

The diverging chart is a deterministic interface view of category-change evidence, not another agent or model-planned operation. It has SVG/CSV exports but no separate persisted HTML report. Visualization-specialist reports retain their approved evidence mappings.

## Result labels

Recorded example, Analysis reviewed, Documentation searched, No data queried, No numerical result and Inspect verification describe distinct outcomes. A document search does not establish that a policy was found or that business data was queried. Detailed checks and the AI verdict remain available in the evidence view.

## Checks

```bash
python presentation_checks.py
python answer_completeness_checks.py
python deployment_checks.py
node presentation_checks.js
```

The JavaScript check uses Node and is included in CI. Offline regressions, simulated DOM tests and rendered chart fixtures cover specific presentation behavior; they do not establish every hosted interaction or fresh model output.

Browser checks should cover range totals and peaks, positive/negative category contributions, omitted groups, new saved reports, status labels, mobile layout, keyboard focus and private chart access. Old stored HTML reports do not change retrospectively.
