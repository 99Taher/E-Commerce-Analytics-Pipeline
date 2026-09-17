-- =============================================================
-- Retail Sales Data Warehouse — Database Initialization
-- =============================================================
-- This script runs automatically when the PostgreSQL container
-- starts for the first time. It creates:
--   1. The Airflow metadata database + user
--   2. Three schemas in the retail_dw database for the pipeline
-- =============================================================

-- -----------------------------------------
-- 1. Create Airflow metadata database & user
-- -----------------------------------------
CREATE USER airflow_user WITH PASSWORD 'airflow_pass_2024';
CREATE DATABASE airflow_db OWNER airflow_user;
GRANT ALL PRIVILEGES ON DATABASE airflow_db TO airflow_user;

-- -----------------------------------------
-- 2. Create schemas in the retail_dw database
-- -----------------------------------------

-- RAW schema: landing zone for ingested CSV data
-- Data arrives here exactly as extracted, with minimal transformation
CREATE SCHEMA IF NOT EXISTS raw;
COMMENT ON SCHEMA raw IS 'Landing zone for raw ingested data from CSV files';

-- STAGING schema: cleaned and validated data (managed by dbt)
-- Business rules applied, data types cast, duplicates removed
CREATE SCHEMA IF NOT EXISTS staging;
COMMENT ON SCHEMA staging IS 'Cleaned and validated data managed by dbt staging models';

-- WAREHOUSE schema: star schema dimensional model (managed by dbt)
-- Fact and dimension tables for analytical queries
CREATE SCHEMA IF NOT EXISTS warehouse;
COMMENT ON SCHEMA warehouse IS 'Star schema data warehouse with fact and dimension tables';

-- -----------------------------------------
-- 3. Create raw tables for ETL loading
-- -----------------------------------------

-- Sales transactions table (Part 1 of CSV: 18,635 rows)
CREATE TABLE IF NOT EXISTS raw.sales_transactions (
    id                  SERIAL PRIMARY KEY,
    transaction_date    DATE,
    month_year          VARCHAR(20),
    customer_name       VARCHAR(200),
    style               VARCHAR(50),
    sku                 VARCHAR(100),
    size                VARCHAR(20),
    quantity            NUMERIC(10, 2),
    unit_price          NUMERIC(12, 2),
    gross_amount        NUMERIC(12, 2),
    loaded_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_sales_date ON raw.sales_transactions(transaction_date);
CREATE INDEX idx_sales_customer ON raw.sales_transactions(customer_name);
CREATE INDEX idx_sales_sku ON raw.sales_transactions(sku);

COMMENT ON TABLE raw.sales_transactions IS 'Raw sales transactions extracted from CSV Part 1';

-- Stock/Inventory table (Part 2 of CSV: 17,756 rows)
CREATE TABLE IF NOT EXISTS raw.stock_inventory (
    id                  SERIAL PRIMARY KEY,
    transaction_date    DATE,
    month_year          VARCHAR(20),
    customer_name       VARCHAR(200),
    style               VARCHAR(50),
    sku                 VARCHAR(100),
    quantity            NUMERIC(10, 2),
    unit_price          NUMERIC(12, 2),
    gross_amount        NUMERIC(12, 2),
    stock               INTEGER,
    loaded_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_stock_date ON raw.stock_inventory(transaction_date);
CREATE INDEX idx_stock_sku ON raw.stock_inventory(sku);

COMMENT ON TABLE raw.stock_inventory IS 'Raw stock/inventory data extracted from CSV Part 2';

-- -----------------------------------------
-- 4. ETL metadata tracking table
-- -----------------------------------------
CREATE TABLE IF NOT EXISTS raw.etl_log (
    id              SERIAL PRIMARY KEY,
    run_id          VARCHAR(50) NOT NULL,
    step            VARCHAR(50) NOT NULL,
    status          VARCHAR(20) NOT NULL,  -- 'started', 'success', 'failed'
    rows_processed  INTEGER,
    details         TEXT,
    started_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at    TIMESTAMP
);

COMMENT ON TABLE raw.etl_log IS 'ETL pipeline execution log for monitoring and debugging';

-- -----------------------------------------
-- 5. Grant privileges
-- -----------------------------------------
GRANT ALL PRIVILEGES ON SCHEMA raw TO retail_user;
GRANT ALL PRIVILEGES ON SCHEMA staging TO retail_user;
GRANT ALL PRIVILEGES ON SCHEMA warehouse TO retail_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA raw TO retail_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA raw TO retail_user;
