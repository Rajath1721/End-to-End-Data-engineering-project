"""Small PIN-based sales and inventory dashboard for the sample project."""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "data" / "warehouse" / "retail.db"

st.set_page_config(page_title="Retail Location Lookup", page_icon="📍", layout="wide")
st.title("Retail sales and stock by PIN")
st.caption("Enter a demo store PIN to see its sample sales history and latest stock snapshot.")
st.warning("Practice data only: the sales, stock, and demo stores shown here are not PAI operational data.")


def read_query(sql: str, params: tuple = ()) -> pd.DataFrame:
    with sqlite3.connect(f"{DB_PATH.resolve().as_uri()}?mode=ro", uri=True) as connection:
        return pd.read_sql_query(sql, connection, params=params)


with st.form("pin_lookup"):
    pincode = st.text_input("Store PIN code", value="560041", max_chars=6,
                            help="Try 560041 for Jayanagar or 560100 for Electronic City.").strip()
    submitted = st.form_submit_button("Search")

if not DB_PATH.exists():
    st.info("First create, check, and load the sample data. Follow steps 2–4 in step.md.")
elif submitted:
    if not re.fullmatch(r"\d{6}", pincode):
        st.error("Enter a six-digit PIN code.")
    else:
        stores = read_query(
            "SELECT DISTINCT store_id, store_name, locality, state FROM sales_daily "
            "WHERE pincode = ? ORDER BY store_id", (pincode,),
        )
        if stores.empty:
            st.warning(f"No demo store is mapped to PIN {pincode}.")
        else:
            sales = read_query(
                "SELECT product_id, product_name, category, SUM(net_units_sold) AS net_units_sold, "
                "ROUND(SUM(net_sales_inr), 2) AS net_sales_inr "
                "FROM sales_daily WHERE pincode = ? "
                "GROUP BY product_id, product_name, category ORDER BY net_sales_inr DESC", (pincode,),
            )
            dates = read_query(
                "SELECT MIN(sale_date) AS first_day, MAX(sale_date) AS last_day "
                "FROM sales_daily WHERE pincode = ?", (pincode,),
            ).iloc[0]
            stock_date = read_query(
                "SELECT MAX(snapshot_date) AS snapshot_date FROM inventory_snapshot WHERE pincode = ?",
                (pincode,),
            ).iloc[0]["snapshot_date"]
            inventory = read_query(
                "SELECT store_id, product_name, category, on_hand_units "
                "FROM inventory_snapshot WHERE pincode = ? AND snapshot_date = ? "
                "ORDER BY store_id, product_name", (pincode, stock_date),
            )

            locality = ", ".join(sorted(stores["locality"].unique()))
            store_names = ", ".join(stores["store_name"].tolist())
            st.subheader(f"{locality} · PIN {pincode}")
            st.write(f"Demo store(s): {store_names}")
            st.caption(f"Sales history: {dates['first_day']} to {dates['last_day']}")

            total_sales = float(sales["net_sales_inr"].sum())
            total_units = int(sales["net_units_sold"].sum())
            left, right = st.columns(2)
            left.metric("Net sales in sample history", f"₹{total_sales:,.2f}")
            right.metric("Net units sold", f"{total_units:,}")

            st.subheader("Sales by product")
            st.bar_chart(sales.set_index("product_name")["net_sales_inr"])
            st.dataframe(sales, hide_index=True, use_container_width=True)

            st.subheader(f"Latest stock snapshot · {stock_date}")
            st.dataframe(inventory, hide_index=True, use_container_width=True)

st.divider()
st.caption("This PIN means the demo store's physical location. Sales by customer delivery PIN needs order-level delivery data.")
