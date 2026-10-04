import csv
from pathlib import Path

import psycopg
from psycopg import sql

RAW = Path(__file__).parent / "data" / "raw"

FILES = {
    "customers": "olist_customers_dataset.csv",
    "geolocation": "olist_geolocation_dataset.csv",
    "order_items": "olist_order_items_dataset.csv",
    "order_payments": "olist_order_payments_dataset.csv",
    "order_reviews": "olist_order_reviews_dataset.csv",
    "orders": "olist_orders_dataset.csv",
    "products": "olist_products_dataset.csv",
    "sellers": "olist_sellers_dataset.csv",
    "category_translations": "product_category_name_translation.csv",
}

# Check every source file before changing the database.
sources = {}
for table, filename in FILES.items():
    path = RAW / filename
    with path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.reader(source)
        columns = next(reader)
        row_count = sum(1 for _ in reader)
    sources[table] = (path, columns, row_count)

with psycopg.connect(
    host="localhost",
    port=5432,
    dbname="causyn",
    user="aman",
) as connection:
    with connection.cursor() as cursor:
        cursor.execute("CREATE SCHEMA IF NOT EXISTS raw")

        for table, (path, columns, expected_rows) in sources.items():
            target = sql.Identifier("raw", table)

            definitions = sql.SQL(", ").join(
                sql.SQL("{} TEXT").format(sql.Identifier(column))
                for column in columns
            )

            cursor.execute(
                sql.SQL("CREATE TABLE IF NOT EXISTS {} ({})").format(
                    target, definitions
                )
            )

            # Replace this raw copy on reruns to prevent duplicate loading.
            cursor.execute(sql.SQL("TRUNCATE TABLE {}").format(target))

            copy_command = sql.SQL(
                "COPY {} ({}) FROM STDIN WITH (FORMAT CSV, HEADER TRUE)"
            ).format(
                target,
                sql.SQL(", ").join(map(sql.Identifier, columns)),
            )

            with path.open(encoding="utf-8-sig", newline="") as source:
                with cursor.copy(copy_command) as copy:
                    while chunk := source.read(1024 * 1024):
                        copy.write(chunk)

            cursor.execute(
                sql.SQL("SELECT COUNT(*) FROM {}").format(target)
            )
            loaded_rows = cursor.fetchone()[0]

            if loaded_rows != expected_rows:
                raise ValueError(
                    f"{table}: expected {expected_rows}, "
                    f"loaded {loaded_rows}"
                )

            print(f"Verified raw.{table}: {loaded_rows:,} rows")

print("\nSuccess: all nine tables loaded and committed.")