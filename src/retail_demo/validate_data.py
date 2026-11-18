"""Validate landed sales and inventory CSVs without changing the source files."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]

SALES_REQUIRED = [
    "sale_date", "store_id", "store_name", "locality", "pincode", "state", "product_id", "product_name",
    "category", "brand", "units_sold", "return_units", "net_units_sold",
    "unit_price_inr", "net_sales_inr",
]
INVENTORY_REQUIRED = [
    "snapshot_date", "store_id", "store_name", "locality", "pincode", "state", "product_id", "product_name",
    "category", "brand", "on_hand_units", "lead_time_days",
]


def validate_file(path: Path, required: list[str], date_col: str, numeric_cols: list[str],
                  integer_cols: list[str], key_cols: list[str], kind: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (accepted, quarantined); every rejected row gets a reason code."""
    df = pd.read_csv(path, dtype="string", keep_default_na=False)
    missing_columns = sorted(set(required) - set(df.columns))
    if missing_columns:
        raise ValueError(f"{path.name} is missing required columns: {', '.join(missing_columns)}")

    reasons = pd.Series("", index=df.index, dtype="string")

    def flag(mask: pd.Series, code: str) -> None:
        mask = mask.fillna(False)
        reasons.loc[mask] = reasons.loc[mask].map(lambda old: f"{old};{code}" if old else code)

    for col in required:
        flag(df[col].str.strip().eq(""), f"missing_{col}")

    parsed_date = pd.to_datetime(df[date_col], errors="coerce")
    flag(parsed_date.isna(), f"invalid_{date_col}")
    if "pincode" in df.columns:
        flag(~df["pincode"].str.fullmatch(r"\d{6}"), "invalid_pincode")

    numbers: dict[str, pd.Series] = {}
    for col in numeric_cols:
        raw = df[col].str.strip()
        value = pd.to_numeric(raw, errors="coerce")
        numbers[col] = value
        flag(value.isna(), f"invalid_{col}")
        if col in integer_cols:
            fractional = value.notna() & ~np.isclose(value.fillna(0) % 1, 0)
            flag(fractional, f"non_integer_{col}")

    flag(df.duplicated(key_cols, keep=False), "duplicate_business_key")

    if kind == "sales":
        flag(numbers["units_sold"] < 0, "negative_units_sold")
        flag(numbers["return_units"] > 0, "return_units_must_be_zero_or_negative")
        flag(numbers["return_units"].abs() > numbers["units_sold"], "returns_exceed_units_sold")
        flag(numbers["unit_price_inr"] <= 0, "non_positive_unit_price")
        expected_net = numbers["units_sold"] + numbers["return_units"]
        flag(numbers["net_units_sold"] != expected_net, "net_units_mismatch")
        expected_revenue = (numbers["net_units_sold"] * numbers["unit_price_inr"]).round(2)
        revenue_mismatch = (numbers["net_sales_inr"] - expected_revenue).abs() > 0.01
        flag(revenue_mismatch, "net_sales_mismatch")
    else:
        flag(numbers["on_hand_units"] < 0, "negative_on_hand_units")
        flag(numbers["lead_time_days"] <= 0, "non_positive_lead_time")

    accepted = df.loc[reasons.eq("")].copy()
    quarantined = df.loc[~reasons.eq("")].copy()
    if not quarantined.empty:
        quarantined["validation_errors"] = reasons.loc[~reasons.eq("")]
    return accepted, quarantined


def run() -> None:
    raw_dir = ROOT / "data" / "raw"
    clean_dir = ROOT / "data" / "clean"
    quarantine_dir = ROOT / "data" / "quarantine"
    quality_dir = ROOT / "data" / "quality"
    for directory in (clean_dir, quarantine_dir, quality_dir):
        directory.mkdir(parents=True, exist_ok=True)

    sales_ok, sales_bad = validate_file(
        raw_dir / "pos_sales.csv", SALES_REQUIRED, "sale_date",
        ["units_sold", "return_units", "net_units_sold", "unit_price_inr", "net_sales_inr"],
        ["units_sold", "return_units", "net_units_sold"],
        ["sale_date", "store_id", "product_id"], "sales",
    )
    inventory_ok, inventory_bad = validate_file(
        raw_dir / "inventory.csv", INVENTORY_REQUIRED, "snapshot_date",
        ["on_hand_units", "lead_time_days"], ["on_hand_units", "lead_time_days"],
        ["snapshot_date", "store_id", "product_id"], "inventory",
    )

    sales_ok.to_csv(clean_dir / "sales_clean.csv", index=False)
    inventory_ok.to_csv(clean_dir / "inventory_clean.csv", index=False)
    sales_bad.to_csv(quarantine_dir / "sales_quarantine.csv", index=False)
    inventory_bad.to_csv(quarantine_dir / "inventory_quarantine.csv", index=False)

    report = {
        "run_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "source_data_note": "Synthetic portfolio sample data; not PAI operational data.",
        "sales": {"input_rows": len(sales_ok) + len(sales_bad), "accepted_rows": len(sales_ok), "quarantined_rows": len(sales_bad)},
        "inventory": {"input_rows": len(inventory_ok) + len(inventory_bad), "accepted_rows": len(inventory_ok), "quarantined_rows": len(inventory_bad)},
    }
    (quality_dir / "validation_report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"Sales: {len(sales_ok):,} accepted, {len(sales_bad):,} quarantined")
    print(f"Inventory: {len(inventory_ok):,} accepted, {len(inventory_bad):,} quarantined")
    print(f"Quality report: {quality_dir / 'validation_report.json'}")


if __name__ == "__main__":
    run()
