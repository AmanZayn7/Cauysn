"""Local evidence verification; no model calls or database access.

Numerical claims must explicitly identify their evidence, metric, units and
purchase-month scope. These checks do not parse or verify free-text prose.
"""

import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def check_document_citations(result: dict) -> dict:
    allowed = set()

    for event in result["evidence"]:
        if event["tool"] != "search_metric_dictionary":
            continue

        for match in event["result"].get("matches", []):
            allowed.add((
                match["source"].strip(),
                match["section_id"].strip(),
                match["section"].strip(),
            ))

    citations = [
        tuple(part.strip() for part in match)
        for match in re.findall(
            r"\[([^\[\]|]+)\|([^\[\]|]+)\|([^\[\]|]+)\]",
            result["answer"],
        )
    ]

    invalid = [
        " | ".join(citation)
        for citation in citations
        if citation not in allowed
    ]

    if invalid:
        status = "FAIL"
    elif citations:
        status = "PASS"
    else:
        status = "NOT_CHECKED"

    return {
        "check": "Document citation references",
        "status": status,
        "citations_found": len(citations),
        "invalid_references": invalid,
        "limitation": (
            "Checks references in the expected citation format only. "
            "Does not verify claim support or numerical correctness."
        ),
    }


# Explicit allowlist: unknown metrics/units cannot acquire a PASS by coincidence.
METRIC_UNITS = {
    "get_monthly_metrics": {
        "delivered_orders": "orders",
        "delivered_merchandise_value": "BRL",
        "average_merchandise_value_per_order": "BRL",
        "assessable_delivery_orders": "orders",
        "late_orders": "orders",
        "late_delivery_pct": "percent",
    },
    "compare_months": {
        "baseline_merchandise_value": "BRL",
        "comparison_merchandise_value": "BRL",
        "change_value": "BRL",
        "change_pct": "percent",
        "order_count_change": "orders",
        "late_delivery_change_percentage_points": "percentage_points",
    },
    "get_category_changes": {
        "overall_change": "BRL",
        "baseline_value": "BRL",
        "comparison_value": "BRL",
        "change_value": "BRL",
    },
}
SCOPE = "delivered_orders_by_purchase_month"


def _number(value):
    # Floats introduce avoidable uncertainty in structured financial claims.
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
        raise ValueError("Expected a decimal string, integer or Decimal.")
    if isinstance(value, str) and not re.fullmatch(r"[+-]?\d+(?:\.\d+)?", value):
        raise ValueError("Use plain decimal numbers without separators or units.")
    try:
        number = Decimal(value)
    except InvalidOperation as error:
        raise ValueError("Invalid number.") from error
    if not number.is_finite():
        raise ValueError("Number must be finite.")
    return number


def _same_displayed_number(actual, expected, unit):
    actual, expected = _number(actual), _number(expected)
    if unit == "orders":
        return actual == actual.to_integral_value() and actual == expected
    return actual == expected.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _month(value):
    if hasattr(value, "isoformat"):
        value = value.isoformat()
    if isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}(?:-01)?", value):
        return value[:7]
    raise ValueError("Missing or invalid evidence month.")


def _event(result, index):
    events = result.get("evidence", [])
    if type(index) is not int or index < 0 or index >= len(events):
        raise ValueError("Invalid evidence index.")
    event = events[index]
    data = event.get("result")
    if event.get("tool") not in METRIC_UNITS:
        raise ValueError("Evidence is not from an approved numerical tool.")
    if not isinstance(data, dict) or "error" in data:
        raise ValueError("Evidence has no successful numerical result.")
    if data.get("currency") != "BRL":
        raise ValueError("Unexpected or missing evidence currency.")
    return event, data


def _claim_expected(result, claim):
    if not isinstance(claim, dict):
        raise ValueError("Claim must be an object.")
    event, data = _event(result, claim.get("evidence_index"))
    tool, metric = event["tool"], claim.get("metric")
    unit = METRIC_UNITS[tool].get(metric)
    if unit is None or claim.get("unit") != unit:
        raise ValueError("Unsupported metric or incorrect unit.")
    if claim.get("scope") != SCOPE:
        raise ValueError("Claim must identify delivered orders by purchase month.")
    arguments = event.get("arguments", {})
    if tool == "get_monthly_metrics":
        row = data.get("metrics", {})
        evidence_month = _month(row.get("purchase_month"))
        if claim.get("purchase_month") != evidence_month or arguments.get("month") != evidence_month:
            raise ValueError("Purchase month does not match evidence and tool arguments.")
    else:
        for field in ("baseline_month", "comparison_month"):
            if claim.get(field) != data.get(field) or arguments.get(field) != data.get(field):
                raise ValueError("Comparison months do not match evidence and tool arguments.")
            _month(data.get(field))
        row = data
        if tool == "get_category_changes" and metric != "overall_change":
            label = claim.get("category_label")
            matches = [item for item in data.get("categories", [])
                       if isinstance(item, dict) and item.get("category_label") == label]
            if not isinstance(label, str) or len(matches) != 1:
                raise ValueError("Category must match exactly one evidence row.")
            row = matches[0]
    if metric not in row or row[metric] is None:
        raise ValueError("Metric has no available numerical evidence.")
    return row[metric], unit


def check_numerical_claims(result: dict) -> dict:
    """Check result['claims']; omission is NOT_CHECKED, never a vacuous PASS.

    Claim example:
      {"evidence_index": 0, "metric": "change_value", "value": "-261732.18",
       "unit": "BRL", "scope": "delivered_orders_by_purchase_month",
       "baseline_month": "2017-11", "comparison_month": "2017-12"}

    Category claims also require category_label. Monthly claims instead require
    purchase_month. Money/rates use two-decimal ROUND_HALF_UP display precision;
    order counts must match exactly. Values retain their signed meaning.
    """
    claims = result.get("claims")
    failures = []
    if claims is None or claims == []:
        status = "NOT_CHECKED"
        count = 0
    elif not isinstance(claims, list):
        status, count = "FAIL", 0
        failures.append({"reason": "claims must be a list"})
    else:
        count = len(claims)
        for index, claim in enumerate(claims):
            try:
                expected, unit = _claim_expected(result, claim)
                if not _same_displayed_number(claim.get("value"), expected, unit):
                    raise ValueError("Signed value differs from evidence at required precision.")
            except (ValueError, InvalidOperation, TypeError, KeyError) as error:
                failures.append({"claim_index": index, "reason": str(error)})
        status = "FAIL" if failures else "PASS"
    return {
        "check": "Structured numerical claims", "status": status,
        "claims_checked": count, "failures": failures,
        "limitation": "Checks only supplied structured claims against tool evidence. "
                      "Does not prove claims cover or agree with all free-text statements, "
                      "nor independently validate the database or establish causality.",
    }


def check_numerical_evidence(result: dict) -> dict:
    """Recompute available arithmetic; do not infer missing data or policy."""
    checks = []

    def record(index, name, passed):
        checks.append({"evidence_index": index, "name": name,
                       "status": "PASS" if passed else "FAIL"})

    for index, event in enumerate(result.get("evidence", [])):
        tool = event.get("tool")
        if tool not in METRIC_UNITS:
            continue
        data = event.get("result")
        if isinstance(data, dict) and "error" in data:
            continue  # Failed calls contain no arithmetic to verify.
        try:
            _, data = _event(result, index)
            if tool == "compare_months":
                baseline = _number(data["baseline_merchandise_value"])
                comparison = _number(data["comparison_merchandise_value"])
                difference = comparison - baseline
                record(index, "Merchandise difference", _number(data["change_value"]) == difference)
                if baseline == 0:
                    record(index, "Undefined percentage on zero baseline", data.get("change_pct") is None)
                else:
                    record(index, "Percentage change", _same_displayed_number(
                        _number(data["change_pct"]).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                        difference / baseline * 100, "percent"))
            elif tool == "get_category_changes":
                rows = data["categories"]
                if not isinstance(rows, list) or not rows:
                    raise ValueError("No category rows.")
                labels = [row["category_label"] for row in rows]
                record(index, "Unique category labels", len(set(labels)) == len(labels))
                record(index, "Every category difference", all(
                    _number(row["comparison_value"]) - _number(row["baseline_value"])
                    == _number(row["change_value"]) for row in rows))
                total = sum((_number(row["change_value"]) for row in rows), Decimal(0))
                record(index, "Category changes sum to overall change", total == _number(data["overall_change"]))
                record(index, "Tool reconciliation flag", data.get("reconciled") is True)
                # Independent cross-tool reconciliation only for the same month pair.
                for other in result.get("evidence", []):
                    other_data = other.get("result", {})
                    if (other.get("tool") == "compare_months" and isinstance(other_data, dict)
                            and "error" not in other_data and all(
                                other_data.get(field) == data.get(field)
                                for field in ("baseline_month", "comparison_month"))):
                        for row_field, total_field in (
                            ("baseline_value", "baseline_merchandise_value"),
                            ("comparison_value", "comparison_merchandise_value"),
                        ):
                            total = sum((_number(row[row_field]) for row in rows), Decimal(0))
                            record(index, f"Category {row_field} matches monthly evidence",
                                   total == _number(other_data[total_field]))
            elif tool == "get_monthly_metrics":
                row = data["metrics"]
                eligible, late = _number(row["assessable_delivery_orders"]), _number(row["late_orders"])
                record(index, "Late-order counts valid", eligible >= 0 and 0 <= late <= eligible
                       and eligible == eligible.to_integral_value() and late == late.to_integral_value())
                if eligible == 0:
                    record(index, "Undefined rate with zero assessable orders", row.get("late_delivery_pct") is None)
                else:
                    record(index, "Late-delivery rate", _same_displayed_number(
                        _number(row["late_delivery_pct"]).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                        late / eligible * 100, "percent"))
        except (ValueError, KeyError, TypeError, InvalidOperation):
            record(index, "Evidence contains required valid numerical fields", False)
    return {
        "check": "Numerical evidence arithmetic",
        "status": ("FAIL" if any(row["status"] == "FAIL" for row in checks)
                   else "PASS" if checks else "NOT_CHECKED"),
        "checks": checks,
        "limitation": "Verifies available arithmetic, not free-text answers or all metrics. "
                      "Order-count and late-rate differences require underlying monthly "
                      "metrics for independent recomputation and are not recomputed here.",
    }


def _self_test():
    import copy
    import unittest

    class VerificationTests(unittest.TestCase):
        def setUp(self):
            args = {"baseline_month": "2017-11", "comparison_month": "2017-12"}
            comparison = {**args, "currency": "BRL", "baseline_merchandise_value": "100.00",
                          "comparison_merchandise_value": "75.00", "change_value": "-25.00",
                          "change_pct": "-25", "order_count_change": -2,
                          "late_delivery_change_percentage_points": "-3.125"}
            categories = {**args, "currency": "BRL", "overall_change": "-25.00", "reconciled": True,
                          "categories": [
                              {"category_label": "a", "baseline_value": "70", "comparison_value": "40", "change_value": "-30"},
                              {"category_label": "b", "baseline_value": "30", "comparison_value": "35", "change_value": "5"}]}
            self.result = {"answer": "", "evidence": [
                {"tool": "compare_months", "arguments": args, "result": comparison},
                {"tool": "get_category_changes", "arguments": args, "result": categories}],
                "claims": [{**args, "scope": SCOPE, "evidence_index": 0,
                            "metric": "change_value", "value": "-25.00", "unit": "BRL"}]}

        def test_valid_claim_and_arithmetic(self):
            self.assertEqual(check_numerical_claims(self.result)["status"], "PASS")
            self.assertEqual(check_numerical_evidence(self.result)["status"], "PASS")

        def test_wrong_sign_rejected(self):
            self.result["claims"][0]["value"] = "25.00"
            self.assertEqual(check_numerical_claims(self.result)["status"], "FAIL")

        def test_wrong_unit_rejected(self):
            self.result["claims"][0]["unit"] = "percent"
            self.assertEqual(check_numerical_claims(self.result)["status"], "FAIL")

        def test_wrong_month_rejected(self):
            self.result["claims"][0]["comparison_month"] = "2018-01"
            self.assertEqual(check_numerical_claims(self.result)["status"], "FAIL")

        def test_wrong_scope_rejected(self):
            self.result["claims"][0]["scope"] = "corporate_revenue"
            self.assertEqual(check_numerical_claims(self.result)["status"], "FAIL")

        def test_failed_evidence_rejected(self):
            self.result["evidence"][0]["result"] = {"error": "Unavailable"}
            self.assertEqual(check_numerical_claims(self.result)["status"], "FAIL")

        def test_missing_claims_not_checked(self):
            del self.result["claims"]
            self.assertEqual(check_numerical_claims(self.result)["status"], "NOT_CHECKED")

        def test_percentage_points_and_rounding(self):
            claim = self.result["claims"][0]
            claim.update(metric="late_delivery_change_percentage_points", value="-3.13", unit="percentage_points")
            self.assertEqual(check_numerical_claims(self.result)["status"], "PASS")
            claim["unit"] = "percent"
            self.assertEqual(check_numerical_claims(self.result)["status"], "FAIL")

        def test_fabricated_metric_rejected(self):
            self.result["claims"][0]["metric"] = "profit"
            self.assertEqual(check_numerical_claims(self.result)["status"], "FAIL")

        def test_category_mapping(self):
            self.result["claims"][0].update(evidence_index=1, category_label="a", value="-30.00")
            self.assertEqual(check_numerical_claims(self.result)["status"], "PASS")
            self.result["claims"][0]["category_label"] = "missing"
            self.assertEqual(check_numerical_claims(self.result)["status"], "FAIL")

        def test_altered_total_rejected(self):
            self.result["evidence"][1]["result"]["overall_change"] = "-24.00"
            self.assertEqual(check_numerical_evidence(self.result)["status"], "FAIL")

        def test_duplicate_category_rejected(self):
            data = self.result["evidence"][1]["result"]
            data["categories"].append(copy.deepcopy(data["categories"][0]))
            self.assertEqual(check_numerical_evidence(self.result)["status"], "FAIL")

        def test_boolean_and_nonfinite_rejected(self):
            for value in (True, "NaN", "Infinity", "25,00"):
                self.result["claims"][0]["value"] = value
                self.assertEqual(check_numerical_claims(self.result)["status"], "FAIL")

        def test_citation_compatibility(self):
            result = {"answer": "Definition [docs/metric_dictionary.md | metric-05 | Late delivery]",
                      "evidence": [{"tool": "search_metric_dictionary", "result": {"matches": [
                          {"source": "docs/metric_dictionary.md", "section_id": "metric-05", "section": "Late delivery"}]}}]}
            self.assertEqual(check_document_citations(result)["status"], "PASS")
            result["answer"] = "Invented [docs/metric_dictionary.md | metric-999 | Invented]"
            self.assertEqual(check_document_citations(result)["status"], "FAIL")

    tests = unittest.defaultTestLoader.loadTestsFromTestCase(VerificationTests)
    return unittest.TextTestRunner(verbosity=2).run(tests).wasSuccessful()


if __name__ == "__main__":
    import argparse
    import json
    import sys
    from pathlib import Path

    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--self-test", action="store_true", help="Run local synthetic tests; no API credit.")
    group.add_argument("--report", type=Path, help="Check evidence in a saved live evaluation report.")
    args = parser.parse_args()
    if args.self_test:
        sys.exit(0 if _self_test() else 1)
    report = json.loads(args.report.read_text(encoding="utf-8"))
    failed = False
    for case in report["cases"]:
        result = case.get("result")
        if not isinstance(result, dict):
            print(f'{case["case"]}: no result available')
            failed = True
            continue
        checks = [check_document_citations(result), check_numerical_evidence(result),
                  check_numerical_claims(result)]
        print(json.dumps({"case": case["case"], "verification": checks}, indent=2))
        failed = failed or any(check["status"] == "FAIL" for check in checks)
    print("No API calls made. NOT_CHECKED means unavailable coverage, not a pass.")
    sys.exit(1 if failed else 0)
