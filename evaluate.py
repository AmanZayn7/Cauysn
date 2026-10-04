"""CAUSYN regression checks. Default: local tools only, no Gemini requests.

Usage:
    python evaluate.py
    python evaluate.py --live
    python evaluate.py --live --case definition

Live checks validate evidence and screen answer text; they do NOT prove that
every claim is supported. Saved answers must still be reviewed by a person.
"""

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from analytics_tools import (
    compare_months, encode_value, get_category_changes, get_monthly_metrics,
)
from document_tools import search_metric_dictionary
from verification import check_document_citations


ROOT = Path(__file__).resolve().parent
LIVE_SUITE_SOFT_LIMIT = Decimal("0.10")
ALLOWED_TOOLS = {
    "investigate_sql", "get_monthly_metrics", "compare_months", "get_category_changes",
    "search_metric_dictionary",
}
QUESTIONS = {
    "definition": "How is late delivery defined?",
    "comparison": (
        "Compare November 2017 with December 2017. Report the merchandise value "
        "change, order count change, late-delivery rate difference, and the three "
        "largest negative category contributions."
    ),
    "unsupported_policy": "What is our refund policy and refund deadline?",
    "missing_dates": "Why did merchandise value decline?",
    "outside_range": "Compare November 2025 with December 2025.",
}


def check(name, passed, detail="", kind="objective"):
    return {"name": name, "status": "PASS" if passed else "FAIL",
            "kind": kind, "detail": detail}


def decimal_matches(actual, expected):
    try:
        return Decimal(str(actual)) == Decimal(str(expected))
    except (ValueError, TypeError, ArithmeticError):
        return False


def comparison_checks(result):
    expected = {
        "baseline_month": "2017-11", "comparison_month": "2017-12",
        "baseline_merchandise_value": "987765.37",
        "comparison_merchandise_value": "726033.19",
        "change_value": "-261732.18", "order_count_change": -1776,
    }
    checks = []
    for key, value in expected.items():
        actual = result.get(key)
        passed = (actual == value if key.endswith("month")
                  else decimal_matches(actual, value))
        checks.append(check(key, passed, f"Expected {value}; got {actual}"))
    for key, expected_value in (
        ("change_pct", Decimal("-26.50")),
        ("late_delivery_change_percentage_points", Decimal("-4.95")),
    ):
        try:
            actual = Decimal(str(result.get(key))).quantize(Decimal("0.01"))
        except (ValueError, TypeError, ArithmeticError):
            actual = None
        checks.append(check(key, actual == expected_value,
                            f"Expected rounded {expected_value}; got {actual}"))
    return checks


def category_checks(result):
    categories = result.get("categories", [])
    checks = [check("Tool reports reconciliation", result.get("reconciled") is True)]
    expected = [
        ("bed_bath_table", "-37876.47"),
        ("computers_accessories", "-32247.65"),
        ("furniture_decor", "-31018.18"),
    ]
    try:
        ordered = sorted(categories, key=lambda row: Decimal(str(row["change_value"])))
        actual_top = [(row["category_label"], Decimal(str(row["change_value"])))
                      for row in ordered[:3]]
        expected_top = [(label, Decimal(value)) for label, value in expected]
        checks.append(check("Three largest negative categories", actual_top == expected_top))
        for field, total in (("baseline_value", "987765.37"),
                             ("comparison_value", "726033.19"),
                             ("change_value", "-261732.18")):
            actual = sum((Decimal(str(row[field])) for row in categories), Decimal(0))
            checks.append(check(f"Category sum: {field}", actual == Decimal(total),
                                f"Expected {total}; got {actual}"))
        checks.append(check("Every category change equals comparison minus baseline", all(
            Decimal(str(row["comparison_value"])) - Decimal(str(row["baseline_value"]))
            == Decimal(str(row["change_value"])) for row in categories
        )))
    except (KeyError, ValueError, TypeError, ArithmeticError):
        checks.append(check("Category evidence has valid structure", False))
    return checks


def local_metrics():
    metrics = get_monthly_metrics("2017-12")["metrics"]
    expected = {"delivered_orders": 5513, "delivered_merchandise_value": "726033.19",
                "assessable_delivery_orders": 5513, "late_orders": 411}
    return [check(key, decimal_matches(metrics.get(key), value),
                  f"Expected {value}; got {metrics.get(key)}")
            for key, value in expected.items()]


def local_bad_dates():
    checks = []
    for month in ("december", "2017-13", "2025-12", "2016-12", "2018-09"):
        try:
            get_monthly_metrics(month)
        except ValueError:
            checks.append(check(f"Reject invalid/unsupported month {month}", True))
        else:
            checks.append(check(f"Reject invalid/unsupported month {month}", False))
    return checks


def local_documents():
    retrieved = search_metric_dictionary("How is late delivery defined?")
    matches = retrieved.get("matches", [])
    matching = [row for row in matches if row.get("section_id") == "metric-05"
                and row.get("source") == "docs/metric_dictionary.md"]
    checks = [check("Retrieve established late-delivery definition", bool(matching))]
    checks.append(check("Refund-policy query returns no candidate evidence",
        search_metric_dictionary("refund policy refund deadline").get("matches") == []))
    if matching:
        row = matching[0]
        evidence = [{"tool": "search_metric_dictionary", "arguments": {}, "result": retrieved}]
        citation = f'[{row["source"]} | {row["section_id"]} | {row["section"]}]'
        valid = check_document_citations({"answer": f"Definition {citation}", "evidence": evidence})
        invalid = check_document_citations({
            "answer": "Invented [docs/metric_dictionary.md | metric-999 | Invented]",
            "evidence": evidence,
        })
        checks.extend([
            check("Accept a retrieved citation reference", valid.get("status") == "PASS"),
            check("Reject an invented citation reference", invalid.get("status") == "FAIL"),
        ])
    return checks


def run_local():
    cases = []
    functions = [
        ("monthly_metrics", local_metrics),
        ("monthly_comparison", lambda: comparison_checks(compare_months("2017-11", "2017-12"))),
        ("category_reconciliation", lambda: category_checks(get_category_changes("2017-11", "2017-12"))),
        ("date_validation", local_bad_dates),
        ("documents_and_citations", local_documents),
    ]
    for name, function in functions:
        print(f"LOCAL: {name}", flush=True)
        started = time.monotonic()
        try:
            checks = function()
        except Exception as error:
            # Do not copy connection strings or sensitive exception bodies into reports.
            checks = [check("Local check completed", False, type(error).__name__)]
        cases.append({"case": name, "checks": checks,
                      "elapsed_seconds": round(time.monotonic() - started, 2)})
    return cases


def live_checks(name, result):
    evidence = result.get("evidence", [])
    answer = result.get("answer", "")
    checks = [
        check("Nonblank answer", isinstance(answer, str) and bool(answer.strip())),
        check("Only approved tools requested", all(row.get("tool") in ALLOWED_TOOLS for row in evidence)),
        check("Tool calls within limit", 0 <= result.get("tool_calls", -1) <= 6),
    ]
    successful = [row for row in evidence if isinstance(row.get("result"), dict)
                  and "error" not in row["result"]]
    if name == "definition":
        citation = check_document_citations(result)
        checks.append(check("Retrieved document citation references valid", citation.get("status") == "PASS"))
        checks.append(check("Definition wording present", bool(re.search(
            r"actual.*delivery.*(?:later|after).*estimated", answer, re.I | re.S)),
            kind="text_screen"))
    elif name == "comparison":
        checks.extend([
            check("SQL specialist delegation completed", any(
                row.get("specialist") == "sql_specialist" and row.get("status") == "complete"
                for row in result.get("agent_trace", [])
            )),
            check("Structured numerical claims verified", result.get("numerical_check", {}).get("status") == "PASS"),
            check("Numerical evidence arithmetic verified", result.get("evidence_check", {}).get("status") == "PASS"),
        ])
        for tool, validate in (("compare_months", comparison_checks),
                               ("get_category_changes", category_checks)):
            rows = [row for row in successful if row.get("tool") == tool]
            checks.append(check(f"Successful {tool} evidence", bool(rows)))
            for row in rows:
                args = row.get("arguments", {})
                checks.append(check(f"Correct months for {tool}", args.get("baseline_month") == "2017-11"
                                    and args.get("comparison_month") == "2017-12"))
                checks.extend(validate(row["result"]))
        # Presence alone cannot establish sign, units, scope or semantic support.
        numeric_text = re.sub(r"(?<=\d),(?=\d)", "", answer)
        checks.append(check("Expected rounded figures appear in answer", all(
            value in numeric_text for value in
            ("261732.18", "26.50", "1776", "4.95", "37876.47", "32247.65", "31018.18")
        ), kind="text_screen"))
        checks.append(check("Percentage-point wording present", bool(re.search(
            r"percentage[ -]points?", answer, re.I)), kind="text_screen"))
    elif name == "unsupported_policy":
        searches = [row for row in evidence if row.get("tool") == "search_metric_dictionary"]
        checks.extend([
            check("Documentation searched", bool(searches)),
            check("At most two document search requests", len(searches) <= 2),
            check("Insufficient documentation acknowledged", bool(re.search(
                r"insufficient|does not contain|no information|not (?:available|documented)|cannot (?:answer|determine)",
                answer, re.I)), kind="text_screen"),
        ])
    elif name == "missing_dates":
        checks.append(check("No numerical tools called before dates supplied", all(
            row.get("tool") == "search_metric_dictionary" for row in evidence)))
        checks.append(check("Requests date clarification", bool(re.search(
            r"(?:specify|provide|which|clarify|what).*?(?:months?|dates?|period)|(?:months?|dates?).*?(?:compare|specify|provide)",
            answer, re.I | re.S)), kind="text_screen"))
    elif name == "outside_range":
        checks.append(check("No successful numerical evidence for unsupported dates", all(
            row.get("tool") == "search_metric_dictionary" for row in successful)))
        checks.append(check("Supported historical range explained", "2017" in answer and "2018" in answer,
                            kind="text_screen"))
    return checks


def run_live(selected):
    from agent import answer_question  # Local mode never imports/initializes the LLM client.
    cases = []
    known_cost = Decimal(0)
    for name in selected:
        if known_cost >= LIVE_SUITE_SOFT_LIMIT:
            print("Suite soft cost threshold reached; remaining cases skipped.")
            break
        print(f"\nLIVE: {name}", flush=True)
        try:
            result = answer_question(QUESTIONS[name])
        except Exception as error:
            cases.append({"case": name, "checks": [check("Live run completed", False,
                          type(error).__name__)], "manual_review_required": True})
            print("Live run failed; stopping suite to avoid repeated paid failures.")
            break
        checks = live_checks(name, result)
        usage = result.get("usage", {})
        complete = usage.get("usage_complete") is True and usage.get("estimated_cost_usd") is not None
        checks.append(check("Complete reported usage available", complete))
        cases.append({"case": name, "question": QUESTIONS[name], "checks": checks,
                      "result": result, "manual_review_required": True})
        if not complete:
            print("Usage is incomplete; stopping suite before another paid case.")
            break
        known_cost += Decimal(str(usage["estimated_cost_usd"]))
        print(f"Reported estimated suite cost so far: USD {known_cost}", flush=True)
    return cases


def run_replay(path):
    """Recheck saved output using current checks; never call the agent/API."""
    original = json.loads(path.read_text(encoding="utf-8"))
    cases = []
    for case in original["cases"]:
        result = case.get("result")
        if not isinstance(result, dict):
            checks = [check("Saved live run completed", False)]
        elif case["case"] not in QUESTIONS:
            checks = [check("Recognized evaluation case", False)]
        else:
            checks = live_checks(case["case"], result)
        cases.append({**case, "checks": checks, "manual_review_required": True})
    return cases, original.get("expected_cases", len(cases))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--live", action="store_true", help="Call Gemini; consumes API credit.")
    mode.add_argument("--replay", type=Path, help="Recheck a saved report; no API calls.")
    parser.add_argument("--case", choices=list(QUESTIONS), help="Run one live case only.")
    args = parser.parse_args()
    if args.case and not args.live:
        parser.error("--case requires --live")
    selected = [args.case] if args.case else list(QUESTIONS)
    if args.replay:
        cases, expected_cases = run_replay(args.replay)
    else:
        cases = run_live(selected) if args.live else run_local()
        expected_cases = len(selected) if args.live else 5
    checks = [item for case in cases for item in case["checks"]]
    failed = sum(item["status"] == "FAIL" for item in checks)
    completed = len(cases) == expected_cases
    report = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "mode": "replay" if args.replay else "live" if args.live else "local",
        "expected_cases": expected_cases, "completed_cases": len(cases),
        "passed_checks": len(checks) - failed, "failed_checks": failed,
        "automated_status": "PASS" if completed and not failed else "FAIL",
        "manual_review_required": bool(args.live or args.replay),
        "limitations": (
            "This is a small regression suite, not an overall accuracy score. "
            "Live text screens check wording/number presence, not complete claim support. "
            "Review scope, signs, units, causal language and unsupported policy claims. "
            "Cost estimates exclude tax/FX and are not hard billing caps."
        ),
        "cases": cases,
    }
    destination = ROOT / "evaluations" / "results"
    destination.mkdir(parents=True, exist_ok=True)
    filename = destination / f'{report["mode"]}_{datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")}.json'
    filename.write_text(json.dumps(report, indent=2, default=encode_value), encoding="utf-8")
    for case in cases:
        for item in case["checks"]:
            print(f'{item["status"]}: {case["case"]} — {item["name"]}')
    print(f'\n{report["automated_status"]}: {report["passed_checks"]} passed; {failed} failed.')
    if args.live or args.replay:
        print("Manual answer review still required; automated PASS is not proof of full correctness.")
        if args.replay:
            print("Replay used saved results; no Gemini API requests made.")
    else:
        print("Local mode made no Gemini API requests.")
    print(f"Report saved: {filename}")
    return 0 if report["automated_status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
