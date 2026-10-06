# Period-total answer fix

Based on the latest uploaded project plus the guided-investigation update. This is a small follow-up update, not a replacement of the whole project.

## Cause and correction

The answer contract required a structured claim for every business figure but only supported row-level claims for range tools. Period totals already existed in validated tool evidence under `reference`; the answer writer could not consistently report them under those rules. The AI reviewer correctly rejected the resulting omission.

The update explicitly supports `aggregation="period_total"` claims for four whitelisted reference metrics, with matching inclusive start/end months and no group identifier. The original range validation and reconciliation run before a reference claim can pass. No sums of overlapping category/seller order counts are used.

Before deterministic checks and AI review, the application adds a short tool-backed section containing merchandise value and unique delivered-order totals for each successful range. Values come from that range's validated reference, not hard-coded full-dataset numbers. Existing invalid claims are not repaired, and original prose remains visible to the reviewer. The verifier can still reject wrong numbers, unsupported causes, incomplete answers, chart problems, or other findings.

No UI, database, model, secrets, timeout, or dependencies are changed. No extra Gemini request or automatic retry is added. Keep `CAUSYN_THINKING_LEVEL=low` in Render; this package addresses the missing-total rejection, not every possible timeout.

## Install and check

Save `causyn_period_totals_fix.zip` in Downloads, then run in your project terminal:

```bash
cd ~/Desktop/causyn
unzip -o ~/Downloads/causyn_period_totals_fix.zip -d .
./.venv/bin/python answer_completeness_checks.py
./.venv/bin/python verification.py --self-test
./.venv/bin/python evaluate_depth.py --self-test
```

These checks are offline and make no API or database requests. The 20-month regression uses a synthetic row distribution with the established total values to test formatting and completeness; it is not a new audit of your real monthly data. Actual hosted Gemini output still requires a smoke test.

## Deploy after checks pass

```bash
git add agent.py verification.py depth_contracts.py verifier_specialist.py answer_completeness.py answer_completeness_checks.py .github/workflows/checks.yml README_PERIOD_TOTALS_FIX.md
git commit -m "Validate and include period totals before answer review"
git push
```

No new Render variable is required. Wait for the new commit to report Live, then run the original monthly-trend prompt once. It should include the tool-backed total merchandise value and delivered orders, alongside the chart and any supported observations. Inspect evidence and review statuses, and verify the chart opens. The original full-window reference values are BRL 13,181,027.13 and 96,211 delivered orders. If it still fails, send the actual review finding; do not weaken verification or repeatedly retry.
