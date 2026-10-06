"""Local evidence verification; no model calls or database access.

Numerical claims must explicitly identify their evidence, metric, units and
purchase-month scope. These checks do not parse or verify free-text prose.
"""

from depth_contracts import TOOLS as DEPTH_TOOLS, PERIOD_TOTAL_UNITS, validate_result as validate_depth_result
import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext


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
    "decompose_merchandise_change": {
        "baseline_orders": "orders", "comparison_orders": "orders",
        "baseline_merchandise_value": "BRL", "comparison_merchandise_value": "BRL",
        "baseline_average_order_value": "BRL", "comparison_average_order_value": "BRL",
        "change_value": "BRL", "volume_effect": "BRL", "average_value_effect": "BRL",
        "reconciliation_difference": "BRL",
    },
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
METRIC_UNITS.update({name: metrics for name, (_, metrics) in DEPTH_TOOLS.items()})
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
    if unit in ("orders", "items"):
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
    aggregation = claim.get('aggregation')
    if aggregation is not None and (tool not in DEPTH_TOOLS or aggregation != 'period_total'):
        raise ValueError('Unsupported claim aggregation.')
    unit = PERIOD_TOTAL_UNITS.get(metric) if aggregation else METRIC_UNITS[tool].get(metric)
    if unit is None or claim.get("unit") != unit:
        raise ValueError("Unsupported metric or incorrect unit.")
    if claim.get("scope") != SCOPE:
        raise ValueError("Claim must identify delivered orders by purchase month.")
    arguments = event.get("arguments", {})
    if tool in DEPTH_TOOLS:
        validate_depth_result(tool,data,arguments)
        for field in ('start_month','end_month'):
            if claim.get(field)!=arguments[field]: raise ValueError('Claim range mismatch.')
        key=DEPTH_TOOLS[tool][0]
        if aggregation == 'period_total':
            if any(field in claim for field in ('purchase_month','category_label','seller_id','customer_state')):
                raise ValueError('Period totals cannot identify a group row.')
            row=data['reference']
        else:
            label=claim.get(key)
            matches=[r for r in data['rows'] if r[key]==label]
            if not isinstance(label,str) or len(matches)!=1: raise ValueError('Claim group mismatch.')
            row=matches[0]
    elif tool == "get_monthly_metrics":
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
            if tool in DEPTH_TOOLS:
                validate_depth_result(tool,data,event.get('arguments',{}))
                record(index, 'Range, group identities, denominators and reference reconciliation', True)
            elif tool == "decompose_merchandise_change":
                inputs = data["inputs"]
                n0, n1 = (_number(inputs[key]["delivered_orders"]) for key in ("baseline", "comparison"))
                v0, v1 = (_number(inputs[key]["delivered_merchandise_value"]) for key in ("baseline", "comparison"))
                if any(n <= 0 or n != n.to_integral_value() for n in (n0, n1)) or min(v0, v1) < 0:
                    raise ValueError("Invalid decomposition inputs.")
                record(index, "Supported decomposition method", data.get("method") == "symmetric_volume_value")
                with localcontext() as context:
                    context.prec = 50
                    a0, a1 = v0 / n0, v1 / n1
                    expected_volume = ((n1-n0)*(a0+a1)/2).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                    expected_value = v1-v0-expected_volume
                    for field, expected in (("baseline_orders",n0),("comparison_orders",n1),
                        ("baseline_merchandise_value",v0),("comparison_merchandise_value",v1),
                        ("change_value",v1-v0),("volume_effect",expected_volume),("average_value_effect",expected_value)):
                        record(index, "Decomposition " + field, _number(data[field]) == expected)
                    for field, expected in (("baseline_average_order_value",a0),("comparison_average_order_value",a1)):
                        record(index, field, _same_displayed_number(_number(data[field]).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),expected,"BRL"))
                residual = _number(data["change_value"]) - _number(data["volume_effect"]) - _number(data["average_value_effect"])
                record(index, "Decomposition reconciles", residual == 0 and _number(data["reconciliation_difference"]) == 0 and data.get("reconciled") is True)
                for side, month_field in (("baseline","baseline_month"),("comparison","comparison_month")):
                    row = inputs[side]
                    record(index, side + " input month", _month(row["purchase_month"]) == data[month_field] == event.get("arguments",{}).get(month_field))
                    matches = [other["result"]["metrics"] for other in result.get("evidence",[])
                        if other.get("tool") == "get_monthly_metrics" and other.get("arguments",{}).get("month") == data[month_field]
                        and isinstance(other.get("result"),dict) and "metrics" in other["result"]]
                    record(index, side + " inputs match monthly evidence", bool(matches) and all(
                        _number(match["delivered_orders"]) == _number(row["delivered_orders"])
                        and _number(match["delivered_merchandise_value"]) == _number(row["delivered_merchandise_value"])
                        for match in matches))
            elif tool == "compare_months":
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

        def decomposition_result(self):
            def monthly(month, count, value):
                return {"currency":"BRL", "metrics":{"purchase_month":month+"-01",
                    "delivered_orders":count,"delivered_merchandise_value":value,
                    "average_merchandise_value_per_order":str(Decimal(value)/count),
                    "assessable_delivery_orders":count,"late_orders":0,"late_delivery_pct":"0"}}
            baseline=monthly("2017-11",10,"100")
            comparison=monthly("2017-12",5,"40")
            args={"baseline_month":"2017-11","comparison_month":"2017-12"}
            data={**args,"currency":"BRL","method":"symmetric_volume_value",
                "baseline_orders":10,"comparison_orders":5,"baseline_merchandise_value":"100",
                "comparison_merchandise_value":"40","baseline_average_order_value":"10",
                "comparison_average_order_value":"8","change_value":"-60","volume_effect":"-45",
                "average_value_effect":"-15","reconciliation_difference":"0","reconciled":True,
                "inputs":{"baseline":baseline["metrics"],"comparison":comparison["metrics"]}}
            return {"answer":"", "evidence":[
                {"tool":"get_monthly_metrics","arguments":{"month":"2017-11"},"result":baseline},
                {"tool":"get_monthly_metrics","arguments":{"month":"2017-12"},"result":comparison},
                {"tool":"decompose_merchandise_change","arguments":args,"result":data}],
                "claims":[{**args,"scope":SCOPE,"evidence_index":2,"metric":"volume_effect","value":"-45.00","unit":"BRL"}]}

        def test_decomposition_valid(self):
            result=self.decomposition_result()
            self.assertEqual(check_numerical_evidence(result)["status"],"PASS")
            self.assertEqual(check_numerical_claims(result)["status"],"PASS")

        def test_decomposition_tampered_component(self):
            result=self.decomposition_result();result["evidence"][2]["result"]["volume_effect"]="-44"
            self.assertEqual(check_numerical_evidence(result)["status"],"FAIL")
            self.assertEqual(check_numerical_claims(result)["status"],"FAIL")

        def test_decomposition_input_disagrees_with_source(self):
            result=self.decomposition_result()
            result["evidence"][2]["result"]["inputs"]["baseline"]=dict(result["evidence"][2]["result"]["inputs"]["baseline"],delivered_orders=9)
            self.assertEqual(check_numerical_evidence(result)["status"],"FAIL")

        def test_decomposition_wrong_method(self):
            result=self.decomposition_result();result["evidence"][2]["result"]["method"]="causal"
            self.assertEqual(check_numerical_evidence(result)["status"],"FAIL")

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
