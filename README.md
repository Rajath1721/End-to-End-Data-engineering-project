# PAI shaped sample sales and inventory data

These are **synthetic sample datasets**, created for a retail data engineering portfolio project. PAI International's public website does not publish transaction-level sales or store-level inventory, so these files are not real PAI records.

New to the project? Start with the beginner-friendly [step-by-step run guide](step.md).

The project also includes a separate PDP crawler for the website's public product catalog. PDP snapshots are catalog data (such as product name, brand, SKU, listed price, and page URL); they are not sales or store inventory.

## Run it in VS Code

Open **Terminal → New Terminal** and make sure the terminal is in the project folder (the one containing this README). Requires Python 3.10+ and `curl` for the website crawler. On macOS, set up the environment once:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Then run these one at a time, in order:

```bash
PYTHONPATH=src python3 -m retail_demo.generate_data --days 540
PYTHONPATH=src python3 -m retail_demo.validate_data
PYTHONPATH=src python3 -m retail_demo.load_sqlite
PYTHONPATH=src python3 -m retail_demo.location_lookup --pincode 560041
```

The first command makes practice sales and stock files. The second checks them. The third saves the clean records in a local database. The fourth shows the Jayanagar demo location's sample sales and latest sample stock. To crawl 25 public product pages, run `PYTHONPATH=src python3 -m retail_demo.crawl_pdp`; that is a separate optional catalog step and needs an internet connection.

After loading the database, open the PIN dashboard with `streamlit run app.py`. Enter a demo store PIN and press **Search**.

## Files

- `data/raw/pos_sales.csv` — daily sales totals by store and product, including returns, net units, net sales, and descriptive fields.
- `data/raw/inventory.csv` — synthetic on-hand inventory snapshot by store and product, with assumed supplier lead times.
- `data/landing/pdp/` — timestamped raw JSONL snapshots collected from public product detail pages.

## Data notes

- Sales grain: one row per date × store × product. 540 days across four demo locations and twelve products (25,920 rows). These are daily aggregates, not receipt-level transactions.
- Inventory grain: one row per store × product for the latest generated snapshot (48 rows).
- Currency is INR. Store names, stock levels, sales, and lead times are invented for demonstration.
- Demo locations include Jayanagar (560041), Electronic City (560100), Hyderabad GPO (500001), and Vijayawada (520001). The postal codes correspond to those areas, but the store records and business data are synthetic and do not claim these are PAI branches. PIN assignments are based on [India Post's public listings](https://www.indiapost.gov.in/).
- `units_sold` is gross sold quantity; `return_units` is zero or a negative returned quantity; `net_units_sold` is their sum; `net_sales_inr` is net units multiplied by unit price.
- Inventory is one synthetic on-hand snapshot per store-product pair. It is not reconstructed from sales history.
- Seeded generation is repeatable. From the project root, run `PYTHONPATH=src python3 -m retail_demo.generate_data --days 540`.

## Validate the sample files

Run `PYTHONPATH=src python3 -m retail_demo.validate_data`. The validator leaves `data/raw/` untouched, writes passing rows to `data/clean/`, failed rows with reason codes to `data/quarantine/`, and a row-count summary to `data/quality/validation_report.json`.

## Crawl public product detail pages

Install the dependencies in `requirements.txt`, then run `PYTHONPATH=src python3 -m retail_demo.crawl_pdp`. It checks PAI's `robots.txt`, discovers PDPs from its sitemap, and crawls up to 25 pages by default with a one-second pause between pages. Snapshots are saved as JSONL under `data/landing/pdp/run_<timestamp>/`, including the raw Product JSON-LD plus normalized fields and crawl time. Use `--limit 0` only when you intentionally want every PDP listed in the sitemap; the current sitemap has several thousand product URLs, so a full crawl takes a while. The crawler records product-page availability when present, but that does not represent stock by store.

## Load into the local SQL database

Run `PYTHONPATH=src python3 -m retail_demo.load_sqlite` after validation. This loads the clean files into `data/warehouse/retail.db`, with one table for daily sales, one for inventory snapshots, and a `mart_daily_category_sales` view that aggregates sales by date, store, and category. SQLite keeps setup local and lightweight; the tables can later be migrated to PostgreSQL.

## Look up a location by PIN

After loading, run `PYTHONPATH=src python3 -m retail_demo.location_lookup --pincode 560041`. The lookup shows sales totals by product for stores mapped to that PIN plus the latest inventory snapshot. This demo treats the PIN as the store's location. Reporting sales by a customer's delivery PIN would require order-level sales data with a customer/delivery PIN field.
