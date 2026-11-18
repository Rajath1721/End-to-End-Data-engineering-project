"""Show sales history and latest sample inventory for a store-location PIN."""
from __future__ import annotations

import argparse
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "data" / "warehouse" / "retail.db"


def lookup(pincode: str) -> int:
    if not re.fullmatch(r"\d{6}", pincode):
        print("Enter a six-digit PIN code, for example 560041.")
        return 2
    if not DB_PATH.exists():
        print("The local database is missing. Generate, validate, and load the sample data first.")
        return 2

    with sqlite3.connect(DB_PATH) as connection:
        connection.row_factory = sqlite3.Row
        stores = connection.execute(
            "SELECT DISTINCT store_id, store_name, locality, pincode "
            "FROM sales_daily WHERE pincode = ? ORDER BY store_id", (pincode,),
        ).fetchall()
        if not stores:
            print(f"No demo store is mapped to PIN code {pincode}.")
            return 1

        date_range = connection.execute(
            "SELECT MIN(sale_date), MAX(sale_date) FROM sales_daily WHERE pincode = ?", (pincode,),
        ).fetchone()
        sales = connection.execute(
            "SELECT product_id, product_name, category, SUM(net_units_sold) AS units, "
            "ROUND(SUM(net_sales_inr), 2) AS sales_inr "
            "FROM sales_daily WHERE pincode = ? "
            "GROUP BY product_id, product_name, category ORDER BY sales_inr DESC", (pincode,),
        ).fetchall()
        snapshot = connection.execute(
            "SELECT MAX(snapshot_date) FROM inventory_snapshot WHERE pincode = ?", (pincode,),
        ).fetchone()[0]
        inventory = connection.execute(
            "SELECT store_id, product_id, product_name, category, on_hand_units "
            "FROM inventory_snapshot WHERE pincode = ? AND snapshot_date = ? "
            "ORDER BY store_id, product_name", (pincode, snapshot),
        ).fetchall()

    total_units = sum(row["units"] for row in sales)
    total_sales = sum(row["sales_inr"] for row in sales)
    localities = ", ".join(sorted({row["locality"] for row in stores}))
    print(f"Location: {localities} | PIN {pincode}")
    print("Stores: " + ", ".join(f"{row['store_id']} ({row['store_name']})" for row in stores))
    print(f"Sales history: {date_range[0]} to {date_range[1]}")
    print(f"Net sales: ₹{total_sales:,.2f} | Net units sold: {total_units:,}")
    print("\nSales by product:")
    for row in sales:
        print(f"  {row['product_name']}: {row['units']:,} units | ₹{row['sales_inr']:,.2f}")
    print(f"\nOn-hand inventory snapshot ({snapshot}):")
    for row in inventory:
        print(f"  {row['store_id']} | {row['product_name']}: {row['on_hand_units']:,} units")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Look up demo sales and inventory by store PIN code")
    parser.add_argument("--pincode", required=True, help="six-digit store-location PIN code")
    args = parser.parse_args()
    raise SystemExit(lookup(args.pincode))
