# Period totals and answer verification

Range tools expose validated period totals under `reference`. Structured claims support `aggregation="period_total"` for four allowed reference metrics, with inclusive start/end months and no group identifier. Range validation and reconciliation run before such a claim can pass.

Before deterministic checks and AI review, the application adds a tool-backed section containing merchandise value and unique delivered-order totals for each successful range. Values come from that range's validated reference. Overlapping category or seller order counts are not summed into a unique-order total.

Original answer prose remains visible to the verifier. Incorrect claims are not automatically repaired; checks and AI review can reject unsupported figures, causes, incomplete answers or chart inconsistencies. This behavior addresses missing totals rather than every possible model or timeout failure.

## Checks

```bash
python answer_completeness_checks.py
python verification.py --self-test
python evaluate_depth.py --self-test
```

These commands run offline. The twenty-month regression uses synthetic row distributions with established baseline totals to test formatting and completeness; it is not a fresh audit of the monthly source data. The reporting baseline is BRL 13,181,027.13 merchandise value and 96,211 delivered orders.

Hosted checks should confirm that a supported range question includes its period totals, chart and review status. Any failure should be investigated through the recorded verification findings; verification rules should not be weakened to accept an answer.
