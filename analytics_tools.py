import json
import sys
from datetime import date
from decimal import Decimal

import psycopg
from psycopg.rows import dict_row


def validate_month(month: str) -> date:
    try:
        selected = date.fromisoformat(f"{month}-01")
    except ValueError:
        raise ValueError("Use YYYY-MM format, such as 2017-12.")

    if month != selected.strftime("%Y-%m"):
        raise ValueError("Use YYYY-MM format, such as 2017-12.")

    if not date(2017, 1, 1) <= selected <= date(2018, 8, 1):
        raise ValueError("Choose a month from 2017-01 through 2018-08.")

    return selected


def connect_database():
    return psycopg.connect(
        host="localhost",
        port=5432,
        dbname="causyn",
        user="causyn_reader",
        row_factory=dict_row,
    )


def get_monthly_metrics(month: str) -> dict:
    selected_month = validate_month(month)

    with connect_database() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
            cursor.execute("SET LOCAL statement_timeout = '10s'")
            cursor.execute(
                """
                SELECT *
                FROM analytics.monthly_performance
                WHERE purchase_month = %s
                """,
                (selected_month,),
            )
            result = cursor.fetchone()

    if result is None:
        raise ValueError("No monthly metrics found for that period.")

    return {
        "currency": "BRL",
        "source": "analytics.monthly_performance",
        "cohort": "Delivered orders grouped by purchase month",
        "metrics": result,
    }


def compare_months(baseline_month: str, comparison_month: str) -> dict:
    baseline = get_monthly_metrics(baseline_month)["metrics"]
    comparison = get_monthly_metrics(comparison_month)["metrics"]

    baseline_value = baseline["delivered_merchandise_value"]
    comparison_value = comparison["delivered_merchandise_value"]
    change = comparison_value - baseline_value

    baseline_late = baseline["late_delivery_pct"]
    comparison_late = comparison["late_delivery_pct"]

    return {
        "currency": "BRL",
        "source": "analytics.monthly_performance",
        "cohort": "Delivered orders grouped by purchase month",
        "baseline_month": baseline_month,
        "comparison_month": comparison_month,
        "baseline_merchandise_value": baseline_value,
        "comparison_merchandise_value": comparison_value,
        "change_value": change,
        "change_pct": (
            change / baseline_value * Decimal("100")
            if baseline_value != 0 else None
        ),
        "order_count_change": (
            comparison["delivered_orders"] - baseline["delivered_orders"]
        ),
        "late_delivery_change_percentage_points": (
            comparison_late - baseline_late
            if comparison_late is not None and baseline_late is not None
            else None
        ),
    }


def get_category_changes(
    baseline_month: str,
    comparison_month: str,
) -> dict:
    comparison = compare_months(baseline_month, comparison_month)
    baseline_date = validate_month(baseline_month)
    comparison_date = validate_month(comparison_month)

    with connect_database() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
            cursor.execute("SET LOCAL statement_timeout = '10s'")
            cursor.execute(
                """
                WITH category_totals AS (
                    SELECT
                        p.category_label,
                        SUM(CASE WHEN
                            DATE_TRUNC('month', o.purchased_at)::date = %s
                            THEN i.merchandise_value ELSE 0
                        END) AS baseline_value,
                        SUM(CASE WHEN
                            DATE_TRUNC('month', o.purchased_at)::date = %s
                            THEN i.merchandise_value ELSE 0
                        END) AS comparison_value
                    FROM staging.order_items i
                    JOIN staging.orders o ON i.order_id = o.order_id
                    JOIN staging.products p ON i.product_id = p.product_id
                    WHERE o.is_delivered
                      AND DATE_TRUNC('month', o.purchased_at)::date
                          IN (%s, %s)
                    GROUP BY p.category_label
                )
                SELECT
                    *,
                    comparison_value - baseline_value AS change_value
                FROM category_totals
                ORDER BY change_value, category_label
                """,
                (
                    baseline_date,
                    comparison_date,
                    baseline_date,
                    comparison_date,
                ),
            )
            categories = cursor.fetchall()

    baseline_total = sum(
        (row["baseline_value"] for row in categories), Decimal("0")
    )
    comparison_total = sum(
        (row["comparison_value"] for row in categories), Decimal("0")
    )

    if (
        baseline_total != comparison["baseline_merchandise_value"]
        or comparison_total != comparison["comparison_merchandise_value"]
    ):
        raise ValueError("Category totals do not reconcile to monthly totals.")

    return {
        "currency": "BRL",
        "baseline_month": baseline_month,
        "comparison_month": comparison_month,
        "source": "staging.order_items + staging.orders + staging.products",
        "metric": "Delivered merchandise value excluding freight",
        "overall_change": comparison["change_value"],
        "reconciled": True,
        "categories": categories,
    }


def encode_value(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, date):
        return value.isoformat()
    raise TypeError(f"Cannot encode {type(value).__name__}")


if __name__ == "__main__":
    try:
        if len(sys.argv) == 3:
            result = compare_months(sys.argv[1], sys.argv[2])
        elif len(sys.argv) <= 2:
            month = sys.argv[1] if len(sys.argv) == 2 else "2017-12"
            result = get_monthly_metrics(month)
        else:
            raise ValueError(
                "Supply one month for metrics or two months for comparison."
            )

        print(json.dumps(result, indent=2, default=encode_value))

    except (ValueError, psycopg.Error) as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)
        