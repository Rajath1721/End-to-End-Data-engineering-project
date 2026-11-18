"""Generate deterministic synthetic daily sales and inventory datasets."""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]


def generate(days: int = 540, seed: int = 42) -> None:
    rng = np.random.default_rng(seed)
    out = ROOT / "data" / "raw"
    out.mkdir(parents=True, exist_ok=True)
    # Demonstration mappings only; these do not claim PAI operates stores here.
    stores = pd.DataFrame([
        ("BLR01", "Jayanagar Demo Store", "Jayanagar", "Karnataka", "560041"),
        ("BLR02", "Electronic City Demo Store", "Electronic City", "Karnataka", "560100"),
        ("HYD01", "Hyderabad Central Demo Store", "Hyderabad GPO", "Telangana", "500001"),
        ("VJA01", "Vijayawada Central Demo Store", "Vijayawada", "Andhra Pradesh", "520001"),
    ], columns=["store_id", "store_name", "locality", "state", "pincode"])
    products = pd.DataFrame([
        ("MOB001", "5G Smartphone 128GB", "Mobiles", "Samsung", 28999, 40, 7),
        ("MOB002", "5G Smartphone 256GB", "Mobiles", "Xiaomi", 24999, 34, 8),
        ("MOB003", "Smartphone 128GB", "Mobiles", "Vivo", 17999, 27, 7),
        ("TV001", "43 inch 4K Smart TV", "Televisions & Audio", "LG", 32999, 15, 12),
        ("TV002", "55 inch 4K Smart TV", "Televisions & Audio", "Samsung", 52999, 11, 12),
        ("AC001", "1.5T Inverter Split AC", "Air Conditioners", "Voltas", 38999, 12, 14),
        ("WM001", "7kg Front Load Washer", "Washing Machines", "IFB", 31999, 9, 14),
        ("REF001", "308L Frost Free Refrigerator", "Refrigerators", "Whirlpool", 35999, 10, 14),
        ("LAP001", "15 inch Performance Laptop", "Laptops & IT", "HP", 62999, 8, 10),
        ("KIT001", "750W Mixer Grinder", "Kitchen Appliances", "Prestige", 3999, 24, 6),
        ("KIT002", "28L Convection Microwave", "Kitchen Appliances", "IFB", 12999, 12, 9),
        ("FUR001", "3 Seater Sofa", "Furniture", "Pai Home", 28999, 5, 21),
    ], columns=["product_id", "product_name", "category", "brand", "unit_price_inr", "base_daily_demand", "lead_time_days"])
    dates = pd.date_range(end=pd.Timestamp.today().normalize() - pd.Timedelta(days=1), periods=days, freq="D")
    rows = []
    for store in stores.itertuples(index=False):
        store_factor = {"BLR01": 1.25, "BLR02": 0.95, "HYD01": 1.1, "VJA01": 0.8}[store.store_id]
        for p in products.itertuples(index=False):
            level = p.base_daily_demand * store_factor
            phase = rng.uniform(0, 2 * np.pi)
            for i, day in enumerate(dates):
                seasonal = 1 + 0.20 * np.sin(2 * np.pi * i / 365 + phase)
                weekend = 1.24 if day.dayofweek >= 5 else 1.0
                sale = 1.65 if (day.month in (10, 11) and day.day in (1, 2, 3, 4, 5, 6, 7)) else 1.0
                monsoon = 1.15 if (p.category == "Air Conditioners" and day.month in (3, 4, 5)) else 1.0
                units_sold = int(rng.poisson(level * seasonal * weekend * sale * monsoon))
                return_units = -1 if units_sold > 0 and rng.random() < 0.008 else 0
                price = round(p.unit_price_inr * rng.uniform(0.96, 1.04), 2)
                rows.append((day.date().isoformat(), store.store_id, store.store_name, store.locality,
                             store.pincode, store.state,
                             p.product_id, p.product_name, p.category, p.brand, units_sold,
                             return_units, units_sold + return_units, price,
                             round((units_sold + return_units) * price, 2)))
    sales = pd.DataFrame(rows, columns=[
        "sale_date", "store_id", "store_name", "locality", "pincode", "state", "product_id", "product_name",
        "category", "brand", "units_sold", "return_units", "net_units_sold",
        "unit_price_inr", "net_sales_inr",
    ])
    # Inventory is an intentionally synthetic current snapshot, not stock reconstructed from POS.
    inv = []
    for s in stores.itertuples(index=False):
        for p in products.itertuples(index=False):
            inv.append((dates[-1].date().isoformat(), s.store_id, s.store_name, s.locality,
                        s.pincode, s.state,
                        p.product_id, p.product_name, p.category, p.brand,
                        int(rng.integers(max(1, p.base_daily_demand), max(5, p.base_daily_demand * 18))),
                        int(p.lead_time_days)))
    pd.DataFrame(inv, columns=[
        "snapshot_date", "store_id", "store_name", "locality", "pincode", "state", "product_id", "product_name",
        "category", "brand", "on_hand_units", "lead_time_days",
    ]).to_csv(out / "inventory.csv", index=False)
    sales.to_csv(out / "pos_sales.csv", index=False)
    print(f"Generated {len(sales):,} synthetic daily sales rows and {len(inv)} inventory rows in {out}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=540)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    generate(args.days, args.seed)
