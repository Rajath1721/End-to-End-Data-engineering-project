# Project steps — beginner guide

This project is a learning demo for retail data. We’ll go one step at a time. You can run each command in the VS Code terminal.

> **Important:** Sales and inventory are made-up practice data. The website crawler collects public product-page details; it cannot see PAI's private sales or store stock.

## 0. Open the project terminal

In VS Code, choose **Terminal → New Terminal**. The terminal should be in this project folder—the folder that contains `README.md`.

To check where you are, run:

```bash
pwd
```

If the printed path ends with `End-End Data engineering project`, you're in the right place.

## 1. Set up Python (once)

These commands create a separate Python environment for this project and install the packages it needs:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

When the environment is active, the terminal prompt usually starts with `(.venv)`. If you open a new terminal later, activate it again with:

```bash
source .venv/bin/activate
```

## 2. Make practice sales and stock files

```bash
PYTHONPATH=src python3 -m retail_demo.generate_data --days 540
```

This creates two CSV files in `data/raw/`:

- `pos_sales.csv`: daily sales totals for each demo store and product.
- `inventory.csv`: one sample stock snapshot for each demo store and product.

One sales row means **one product at one store on one day**. These are not individual receipts.

## 3. Check the files

```bash
PYTHONPATH=src python3 -m retail_demo.validate_data
```

This checks dates, PIN codes, quantities, prices, duplicate rows, and sales math. It leaves the original files in `data/raw/` unchanged. Passing rows go to `data/clean/`; problem rows go to `data/quarantine/` with an explanation. The row counts are saved in `data/quality/validation_report.json`.

## 4. Save the checked data in the local database

```bash
PYTHONPATH=src python3 -m retail_demo.load_sqlite
```

This loads sales and inventory into `data/warehouse/retail.db`. A database is like an organized filing cabinet: tables store the rows so later commands can find them quickly.

## 5. Look up sales and stock by store PIN

```bash
PYTHONPATH=src python3 -m retail_demo.location_lookup --pincode 560041
```

This shows sample sales and the latest sample stock for the Jayanagar demo location. To look up the Electronic City demo location, use:

```bash
PYTHONPATH=src python3 -m retail_demo.location_lookup --pincode 560100
```

The PIN identifies a **demo store location**. It does not mean sales by customer delivery PIN. The sales figures and store records are invented; they do not confirm that PAI has a store at either PIN.

## 6. Use the PIN search screen

After step 4 has loaded the database, start the dashboard:

```bash
streamlit run app.py
```

The browser page lets you type a PIN and see product sales plus the latest stock count for that demo location. Leave the terminal running while you use the page; press `Control+C` in the terminal when you're done.

## 7. Crawl public product pages (optional)

```bash
PYTHONPATH=src python3 -m retail_demo.crawl_pdp --limit 25
```

This visits up to 25 public product detail pages and saves product names, brands, SKUs, listed prices, and the original product data as timestamped JSON under `data/landing/pdp/`. It waits between page requests. This is catalog data—not sales or inventory.

## Run order recap

Run steps 2 → 3 → 4 → 5 in that order. Step 6 starts the dashboard after the database is ready. Step 7 is separate and optional. Run step 1 only when setting up the project for the first time (or recreating the Python environment).

## If something goes wrong

- **`ModuleNotFoundError: retail_demo`** — make sure you are in the project folder and include `PYTHONPATH=src` before the Python command.
- **`No module named pandas` or `bs4`** — activate `.venv` and run `pip install -r requirements.txt`.
- **No demo store mapped to the PIN** — use one of the demo PINs above.
- **Crawler cannot connect** — check your internet connection and try the crawler again later.
