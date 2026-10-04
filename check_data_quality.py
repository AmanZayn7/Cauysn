from pathlib import Path
import pandas as pd

RAW = Path(__file__).parent / "data" / "raw"

files = {
    "customers": "olist_customers_dataset.csv",
    "geolocation": "olist_geolocation_dataset.csv",
    "items": "olist_order_items_dataset.csv",
    "payments": "olist_order_payments_dataset.csv",
    "reviews": "olist_order_reviews_dataset.csv",
    "orders": "olist_orders_dataset.csv",
    "products": "olist_products_dataset.csv",
    "sellers": "olist_sellers_dataset.csv",
    "translations": "product_category_name_translation.csv",
}

# Read as text to preserve IDs and leading zeros in ZIP prefixes.
tables = {
    name: pd.read_csv(RAW / filename, dtype="string")
    for name, filename in files.items()
}

keys = {
    "customers": ["customer_id"],
    "orders": ["order_id"],
    "items": ["order_id", "order_item_id"],
    "payments": ["order_id", "payment_sequential"],
    "products": ["product_id"],
    "sellers": ["seller_id"],
    "translations": ["product_category_name"],
}

for name, table in tables.items():
    print(f"\n--- {name.upper()} ---")
    print(f"Rows: {len(table):,}")
    print(f"Exact duplicate rows: {table.duplicated().sum():,}")

    if name in keys:
        key = keys[name]
        print(f"Missing key rows: {table[key].isna().any(axis=1).sum():,}")
        print(f"Duplicate key rows beyond first: {table.duplicated(key).sum():,}")

    missing = table.isna().sum()
    missing = missing[missing > 0]
    print("Missing values:")
    print(missing.to_string() if not missing.empty else "None")

links = [
    ("orders", "customer_id", "customers", "customer_id"),
    ("items", "order_id", "orders", "order_id"),
    ("items", "product_id", "products", "product_id"),
    ("items", "seller_id", "sellers", "seller_id"),
    ("payments", "order_id", "orders", "order_id"),
    ("reviews", "order_id", "orders", "order_id"),
    ("products", "product_category_name",
     "translations", "product_category_name"),
]

print("\n--- RELATIONSHIP CHECKS ---")
for child, child_key, parent, parent_key in links:
    values = tables[child][child_key]
    known = tables[parent][parent_key].dropna()
    unmatched = values.notna() & ~values.isin(known)
    print(
        f"{child}.{child_key} → {parent}.{parent_key}: "
        f"{unmatched.sum():,} unmatched rows "
        "(missing values excluded)"
    )

print("\n--- MULTIPLE RECORDS PER ORDER ---")
for name in ["items", "payments", "reviews"]:
    counts = tables[name].groupby("order_id").size()
    print(f"{name}: {(counts > 1).sum():,} orders with multiple records")

geo = tables["geolocation"]
print(
    "\nZIP prefixes with multiple location rows: "
    f"{(geo.groupby('geolocation_zip_code_prefix').size() > 1).sum():,}"
)

print("\nCheck complete. No files were changed.")