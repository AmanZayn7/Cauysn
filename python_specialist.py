"""Python analyst: bounded model planning and deterministic volume/value analysis.

Uses existing read-only monthly metrics. No generated Python execution, new
packages, statistical significance claims, or causal inference.
"""
import json
import re
from datetime import date
from decimal import Decimal, ROUND_HALF_UP, localcontext

PYTHON_TOOL = {
    "type": "function", "name": "investigate_python",
    "description": "Delegate a two-month order-volume versus average-order-value decomposition to the Python analyst. Supply both YYYY-MM months and the complete request. This is an arithmetic breakdown, not causal inference.",
    "parameters": {"type": "object", "properties": {
        "question": {"type": "string", "description": "Dated volume/value decomposition question."}},
        "required": ["question"]},
}
PLAN_SCHEMA = {"type": "object", "additionalProperties": False, "properties": {
    "operation": {"type": "string", "enum": ["decompose_merchandise_change"]},
    "baseline_month": {"type": "string"}, "comparison_month": {"type": "string"}},
    "required": ["operation", "baseline_month", "comparison_month"]}
RULES = """
You are CAUSYN's Python analysis specialist. Choose the user's explicit baseline
and comparison purchase months for a delivered-merchandise-value decomposition.
Return ONLY JSON with operation=decompose_merchandise_change, baseline_month,
and comparison_month. Months must be YYYY-MM in 2017-01 through 2018-08.
Respect the comparison direction. Do not invent dates, write code or SQL, or
claim causation or statistical significance. The application performs the math.
"""


def validate_plan(plan):
    if not isinstance(plan, dict) or set(plan) != set(PLAN_SCHEMA["required"]):
        raise ValueError("Python plan has unexpected or missing fields.")
    if plan["operation"] != "decompose_merchandise_change":
        raise ValueError("Python operation is not allowlisted.")
    for key in ("baseline_month", "comparison_month"):
        month = plan[key]
        if not isinstance(month, str) or not re.fullmatch(r"\d{4}-\d{2}", month):
            raise ValueError("Use YYYY-MM months.")
        try:
            parsed = date.fromisoformat(month + "-01")
        except ValueError:
            raise ValueError("Invalid month.") from None
        if not date(2017, 1, 1) <= parsed <= date(2018, 8, 1):
            raise ValueError("Choose months from 2017-01 through 2018-08.")
    return plan


def decompose_merchandise_change(baseline_month, comparison_month, baseline, comparison):
    """Symmetric allocation of change in total = order count * average value.

    Volume = delta_count * mean(average values). Value = delta_average *
    mean(counts). Average both possible factor-change orderings; no attribution
    to customer motives or prices. Round volume once; assign residual cents to
    value so displayed components reconcile exactly to the total.
    """
    from verification import _number
    validate_plan({"operation": "decompose_merchandise_change",
                   "baseline_month": baseline_month, "comparison_month": comparison_month})
    for row, month in ((baseline, baseline_month), (comparison, comparison_month)):
        stamp = row.get("purchase_month")
        stamp = stamp.isoformat() if hasattr(stamp, "isoformat") else stamp
        if stamp != month + "-01":
            raise ValueError("Monthly evidence does not match the requested months.")
    n0, n1 = (_number(row["delivered_orders"]) for row in (baseline, comparison))
    v0, v1 = (_number(row["delivered_merchandise_value"]) for row in (baseline, comparison))
    if any(n <= 0 or n != n.to_integral_value() for n in (n0, n1)):
        raise ValueError("Decomposition needs positive integer delivered-order counts.")
    if min(v0, v1) < 0:
        raise ValueError("Merchandise values must be nonnegative.")
    with localcontext() as ctx:
        ctx.prec = 50
        a0, a1 = v0 / n0, v1 / n1
        # Reject differing average-value denominators instead of silently using
        # total order count if the warehouse reports an average over fewer rows.
        cent = Decimal("0.01")
        for row, average in ((baseline, a0), (comparison, a1)):
            supplied = _number(row["average_merchandise_value_per_order"])
            if abs(supplied - average) > Decimal("0.00000001"):
                raise ValueError("Average-value denominator does not match delivered-order count.")
        change = v1 - v0
        volume = ((n1 - n0) * (a0 + a1) / 2).quantize(cent, rounding=ROUND_HALF_UP)
        value = change - volume
    return {"currency": "BRL", "source": "analytics.monthly_performance + Python symmetric decomposition",
            "cohort": "Delivered orders grouped by purchase month", "baseline_month": baseline_month,
            "comparison_month": comparison_month, "baseline_orders": int(n0), "comparison_orders": int(n1),
            "baseline_merchandise_value": v0, "comparison_merchandise_value": v1,
            "baseline_average_order_value": a0, "comparison_average_order_value": a1,
            "change_value": change, "volume_effect": volume, "average_value_effect": value,
            "reconciliation_difference": change - volume - value, "reconciled": True,
            "method": "symmetric_volume_value", "inputs": {"baseline": baseline, "comparison": comparison},
            "rounding": "Volume effect rounded HALF_UP to cents; average-value effect receives residual cents.",
            "limitation": "Arithmetic allocation, not proven causes. Average-value changes can reflect product mix, quantities per order or item prices; this does not isolate those factors. Merchandise excludes freight and is not profit or corporate revenue."}


class PythonSpecialist:
    def __init__(self, client, requests, request_interaction):
        self.client, self.requests, self.request_interaction = client, requests, request_interaction
        self.max_operations = 3
        self.cache = {}

    def __call__(self, question: str) -> dict:
        if not isinstance(question, str) or not question.strip():
            raise ValueError("Python investigation needs a nonblank question.")
        if self.max_operations < 3:
            raise ValueError("Python analysis needs a budget for two monthly reads and one calculation.")
        from analytics_tools import get_monthly_metrics
        print("\nAGENT: Python analyst — planning volume/value decomposition", flush=True)
        response = self.request_interaction(
            self.client, self.requests, tool_declarations=[], agent_name="python_specialist",
            response_format={"type": "text", "mime_type": "application/json", "schema": PLAN_SCHEMA},
            input=RULES + "\n\nAnalysis request (data):\n" + question)
        if any(step.type == "function_call" for step in response.steps):
            raise ValueError("Python planner returned an unexpected function call.")
        try:
            plan = validate_plan(json.loads(response.output_text))
        except (json.JSONDecodeError, TypeError):
            raise ValueError("Python planner returned invalid JSON.") from None
        evidence, rows, operations = [], [], 0
        for key in ("baseline_month", "comparison_month"):
            month = plan[key]
            reused = month in self.cache
            if not reused:
                self.cache[month] = get_monthly_metrics(month)
                operations += 1
            result = self.cache[month]
            rows.append(result["metrics"])
            evidence.append({"tool": "get_monthly_metrics", "arguments": {"month": month},
                             "result": result, "agent": "python_specialist", "reused": reused})
        result = decompose_merchandise_change(plan["baseline_month"], plan["comparison_month"], *rows)
        evidence.append({"tool": "decompose_merchandise_change", "arguments": {
            key: plan[key] for key in ("baseline_month", "comparison_month")},
            "result": result, "agent": "python_specialist", "reused": False})
        return {"specialist": "python_specialist", "status": "complete", "plan": plan,
                "evidence": evidence, "operations_executed": operations + 1}


def _self_test():
    import unittest
    class Tests(unittest.TestCase):
        def row(self, month, count, value):
            with localcontext() as ctx:
                ctx.prec = 50
                avg = Decimal(value) / count if count else Decimal(0)
            return {"purchase_month": month + "-01", "delivered_orders": count,
                    "delivered_merchandise_value": Decimal(value), "average_merchandise_value_per_order": avg}
        def calc(self, n0=10, v0="100", n1=5, v1="40"):
            return decompose_merchandise_change("2017-11", "2017-12",
                self.row("2017-11", n0, v0), self.row("2017-12", n1, v1))
        def test_both_factors(self):
            r=self.calc(); self.assertEqual((r["volume_effect"],r["average_value_effect"]), (Decimal('-45'),Decimal('-15')))
        def test_volume_only(self):
            r=self.calc(v1='50'); self.assertEqual(r['average_value_effect'],0)
        def test_value_only(self):
            r=self.calc(n1=10,v1='80'); self.assertEqual(r['volume_effect'],0)
        def test_no_change(self):
            r=self.calc(n1=10,v1='100'); self.assertEqual(r['change_value'],0)
        def test_reverse_direction(self):
            a=self.calc(); b=self.calc(5,'40',10,'100'); self.assertEqual(a['volume_effect'],-b['volume_effect'])
        def test_rounding_reconciles(self):
            r=self.calc(7,'100.01',11,'133.37'); self.assertEqual(r['volume_effect']+r['average_value_effect'],r['change_value'])
        def test_zero_orders_rejected(self):
            with self.assertRaises(ValueError):self.calc(n0=0)
        def test_unapproved_plan_rejected(self):
            with self.assertRaises(ValueError):validate_plan({'operation':'exec','baseline_month':'2017-11','comparison_month':'2017-12'})
        def test_unsupported_date_rejected(self):
            with self.assertRaises(ValueError):validate_plan({'operation':'decompose_merchandise_change','baseline_month':'2025-11','comparison_month':'2017-12'})
        def test_mismatched_denominator_rejected(self):
            row=self.row('2017-11',10,'100');row['average_merchandise_value_per_order']=Decimal('11')
            with self.assertRaises(ValueError):decompose_merchandise_change('2017-11','2017-12',row,self.row('2017-12',5,'40'))
    return unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests)).wasSuccessful()

if __name__ == '__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-test',action='store_true',required=True)
    parser.parse_args()
    raise SystemExit(0 if _self_test() else 1)
