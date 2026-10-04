from pathlib import Path
import pandas as pd

RAW = Path(__file__).parent / "data" / "raw"

orders = pd.read_csv(RAW / "olist_orders_dataset.csv", dtype="string")
products = pd.read_csv(RAW / "olist_products_dataset.csv", dtype="string")
translations = pd.read_csv(
    RAW / "product_category_name_translation.csv",
    dtype="string",
)

print("--- ORDER COUNTS BY STATUS ---")
print(orders["order_status"].value_counts().to_string())

print("\n--- MISSING TIMESTAMPS BY STATUS ---")
date_columns = [
    "order_approved_at",
    "order_delivered_carrier_date",
    "order_delivered_customer_date",
]

missing = orders[date_columns].isna()
missing["order_status"] = orders["order_status"]
print(missing.groupby("order_status").sum().to_string())

print("\n--- CATEGORIES WITHOUT ENGLISH TRANSLATIONS ---")
categories = products["product_category_name"]
unmatched = (
    categories.notna()
    & ~categories.isin(translations["product_category_name"].dropna())
)
print(categories[unmatched].value_counts().to_string())