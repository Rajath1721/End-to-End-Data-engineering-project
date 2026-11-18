CREATE VIEW IF NOT EXISTS mart_daily_category_sales AS
SELECT sale_date, store_id, store_name, locality, pincode, state, category,
       SUM(units_sold) AS gross_units,
       SUM(return_units) AS return_units,
       SUM(net_units_sold) AS net_units_sold,
       ROUND(SUM(net_sales_inr), 2) AS net_sales_inr
FROM sales_daily
GROUP BY sale_date, store_id, store_name, locality, pincode, state, category;
