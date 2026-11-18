CREATE TABLE IF NOT EXISTS sales_daily (
    sale_date TEXT NOT NULL,
    store_id TEXT NOT NULL,
    store_name TEXT NOT NULL,
    locality TEXT NOT NULL,
    pincode TEXT NOT NULL,
    state TEXT NOT NULL,
    product_id TEXT NOT NULL,
    product_name TEXT NOT NULL,
    category TEXT NOT NULL,
    brand TEXT NOT NULL,
    units_sold INTEGER NOT NULL,
    return_units INTEGER NOT NULL,
    net_units_sold INTEGER NOT NULL,
    unit_price_inr REAL NOT NULL,
    net_sales_inr REAL NOT NULL,
    PRIMARY KEY (sale_date, store_id, product_id)
);

CREATE TABLE IF NOT EXISTS inventory_snapshot (
    snapshot_date TEXT NOT NULL,
    store_id TEXT NOT NULL,
    store_name TEXT NOT NULL,
    locality TEXT NOT NULL,
    pincode TEXT NOT NULL,
    state TEXT NOT NULL,
    product_id TEXT NOT NULL,
    product_name TEXT NOT NULL,
    category TEXT NOT NULL,
    brand TEXT NOT NULL,
    on_hand_units INTEGER NOT NULL,
    lead_time_days INTEGER NOT NULL,
    PRIMARY KEY (snapshot_date, store_id, product_id)
);
