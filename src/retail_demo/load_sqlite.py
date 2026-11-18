"""Load validated CSVs into a local SQLite warehouse."""
from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "sql" / "schema.sql"
DB_PATH = ROOT / "data" / "warehouse" / "retail.db"

SALES_COLUMNS = [
    "sale_date", "store_id", "store_name", "locality", "pincode", "state", "product_id", "product_name",
    "category", "brand", "units_sold", "return_units", "net_units_sold",
    "unit_price_inr", "net_sales_inr",
]
INVENTORY_COLUMNS = [
    "snapshot_date", "store_id", "store_name", "locality", "pincode", "state", "product_id", "product_name",
    "category", "brand", "on_hand_units", "lead_time_days",
]


def read_csv_rows(path: Path, columns: list[str], integer_columns: set[str],
                  real_columns: set[str]) -> list[tuple]:
    with path.open(newline="", encoding="utf-8") as source:
        reader = csv.DictReader(source)
        missing = set(columns) - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{path.name} is missing columns: {', '.join(sorted(missing))}")
        result = []
        for row in reader:
            values = []
            for column in columns:
                value = row[column]
                if column in integer_columns:
                    value = int(value)
                elif column in real_columns:
                    value = float(value)
                values.append(value)
            result.append(tuple(values))
    return result


def run() -> None:
    clean_dir = ROOT / "data" / "clean"
    sales_path = clean_dir / "sales_clean.csv"
    inventory_path = clean_dir / "inventory_clean.csv"
    if not sales_path.exists() or not inventory_path.exists():
        raise FileNotFoundError("Run the validator first: python -m retail_demo.validate_data")

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    sales_rows = read_csv_rows(
        sales_path, SALES_COLUMNS,
        {"units_sold", "return_units", "net_units_sold"},
        {"unit_price_inr", "net_sales_inr"},
    )
    inventory_rows = read_csv_rows(
        inventory_path, INVENTORY_COLUMNS,
        {"on_hand_units", "lead_time_days"}, set(),
    )
    sales_marks = ", ".join("?" for _ in SALES_COLUMNS)
    inventory_marks = ", ".join("?" for _ in INVENTORY_COLUMNS)
    sales_columns = ", ".join(SALES_COLUMNS)
    inventory_columns = ", ".join(INVENTORY_COLUMNS)

    with sqlite3.connect(DB_PATH) as connection:
        connection.executescript(SCHEMA.read_text(encoding="utf-8"))
        # Keep a previously created local demo database compatible with the
        # newly added location fields.
        for table in ("sales_daily", "inventory_snapshot"):
            existing = {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
            if "locality" not in existing:
                connection.execute(f"ALTER TABLE {table} ADD COLUMN locality TEXT NOT NULL DEFAULT ''")
            if "pincode" not in existing:
                connection.execute(f"ALTER TABLE {table} ADD COLUMN pincode TEXT NOT NULL DEFAULT ''")
        connection.execute("DROP VIEW IF EXISTS mart_daily_category_sales")
        connection.executescript((ROOT / "sql" / "daily_sales_mart.sql").read_text(encoding="utf-8"))
        # Rebuild is repeatable: a rerun replaces these two tables' contents.
        connection.execute("DELETE FROM sales_daily")
        connection.execute("DELETE FROM inventory_snapshot")
        connection.executemany(
            f"INSERT INTO sales_daily ({sales_columns}) VALUES ({sales_marks})", sales_rows
        )
        connection.executemany(
            f"INSERT INTO inventory_snapshot ({inventory_columns}) VALUES ({inventory_marks})", inventory_rows
        )
        sales_count = connection.execute("SELECT COUNT(*) FROM sales_daily").fetchone()[0]
        inventory_count = connection.execute("SELECT COUNT(*) FROM inventory_snapshot").fetchone()[0]
        mart_count = connection.execute("SELECT COUNT(*) FROM mart_daily_category_sales").fetchone()[0]

    print(f"Loaded {sales_count:,} sales rows and {inventory_count:,} inventory rows")
    print(f"Reporting view contains {mart_count:,} daily store-category rows")
    print(f"SQLite database: {DB_PATH}")


if __name__ == "__main__":
    run()
