"""
Load module — Loads cleaned DataFrames into PostgreSQL raw schema tables.

Supports two modes:
    - Full load:        TRUNCATE + INSERT (default on first run)
    - Incremental load: INSERT only new rows since the last loaded date

Target tables (created by sql/init/01_create_schemas.sql):
    - raw.sales_transactions
    - raw.stock_inventory
"""

import pandas as pd
import psycopg2.extras
from sqlalchemy import text

from utils import setup_logger, get_engine, get_connection

logger = setup_logger("retail_etl.load")


# ---------------------------------------------------------------------------
# Load functions
# ---------------------------------------------------------------------------
def load_sales(df: pd.DataFrame, engine=None, incremental: bool = False) -> int:
    """
    Load cleaned sales transactions into raw.sales_transactions using batch inserts.

    Args:
        df:           Cleaned sales DataFrame from transform step.
        engine:       SQLAlchemy engine (optional, created if None).
        incremental:  If True, only insert rows newer than the last loaded date.

    Returns:
        Number of rows loaded.
    """
    if engine is None:
        engine = get_engine()

    table = "raw.sales_transactions"

    # Columns to load
    cols = [
        "transaction_date",
        "month_year",
        "customer_name",
        "style",
        "sku",
        "size",
        "quantity",
        "unit_price",
        "gross_amount",
    ]

    load_df = df[cols].copy()

    if incremental:
        last_date = _get_last_loaded_date(engine, table)
        if last_date is not None:
            before = len(load_df)
            load_df = load_df[load_df["transaction_date"] > pd.Timestamp(last_date)]
            logger.info(
                f"Incremental mode: filtering after {last_date}, "
                f"{before} → {len(load_df)} rows"
            )
            if len(load_df) == 0:
                logger.info("No new rows to load.")
                return 0
    else:
        # Full load: truncate first
        logger.info(f"Full load mode: truncating {table}...")
        with engine.begin() as conn:
            conn.execute(text(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE"))

    logger.info(f"Loading {len(load_df):,} rows into {table}...")

    # High-performance bulk insert using psycopg2 execute_values
    records = [
        (
            row["transaction_date"],
            row["month_year"],
            row["customer_name"],
            row["style"],
            row["sku"],
            row["size"],
            float(row["quantity"]) if pd.notnull(row["quantity"]) else None,
            float(row["unit_price"]) if pd.notnull(row["unit_price"]) else None,
            float(row["gross_amount"]) if pd.notnull(row["gross_amount"]) else None,
        )
        for _, row in load_df.iterrows()
    ]

    insert_sql = f"""
        INSERT INTO {table} (
            transaction_date, month_year, customer_name, style, sku, size, quantity, unit_price, gross_amount
        ) VALUES %s
    """

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            psycopg2.extras.execute_values(cur, insert_sql, records, page_size=2000)
        conn.commit()
    finally:
        conn.close()

    actual_count = len(load_df)
    logger.info(f"Successfully loaded {actual_count:,} rows into {table}")
    return actual_count


def load_stock(df: pd.DataFrame, engine=None, incremental: bool = False) -> int:
    """
    Load cleaned stock/inventory data into raw.stock_inventory using batch inserts.

    Args:
        df:           Cleaned stock DataFrame from transform step.
        engine:       SQLAlchemy engine (optional, created if None).
        incremental:  If True, only insert rows newer than the last loaded date.

    Returns:
        Number of rows loaded.
    """
    if engine is None:
        engine = get_engine()

    table = "raw.stock_inventory"

    cols = [
        "transaction_date",
        "month_year",
        "customer_name",
        "style",
        "sku",
        "quantity",
        "unit_price",
        "gross_amount",
        "stock",
    ]

    available_cols = [c for c in cols if c in df.columns]
    load_df = df[available_cols].copy()

    if incremental:
        last_date = _get_last_loaded_date(engine, table)
        if last_date is not None:
            before = len(load_df)
            load_df = load_df[load_df["transaction_date"] > pd.Timestamp(last_date)]
            logger.info(
                f"Incremental mode: filtering after {last_date}, "
                f"{before} → {len(load_df)} rows"
            )
            if len(load_df) == 0:
                logger.info("No new rows to load.")
                return 0
    else:
        logger.info(f"Full load mode: truncating {table}...")
        with engine.begin() as conn:
            conn.execute(text(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE"))

    logger.info(f"Loading {len(load_df):,} rows into {table}...")

    records = [
        (
            row.get("transaction_date"),
            row.get("month_year"),
            row.get("customer_name"),
            row.get("style"),
            row.get("sku"),
            float(row["quantity"]) if pd.notnull(row.get("quantity")) else None,
            float(row["unit_price"]) if pd.notnull(row.get("unit_price")) else None,
            float(row["gross_amount"]) if pd.notnull(row.get("gross_amount")) else None,
            int(row["stock"]) if pd.notnull(row.get("stock")) else None,
        )
        for _, row in load_df.iterrows()
    ]

    insert_sql = f"""
        INSERT INTO {table} (
            transaction_date, month_year, customer_name, style, sku, quantity, unit_price, gross_amount, stock
        ) VALUES %s
    """

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            psycopg2.extras.execute_values(cur, insert_sql, records, page_size=2000)
        conn.commit()
    finally:
        conn.close()

    actual_count = len(load_df)
    logger.info(f"Successfully loaded {actual_count:,} rows into {table}")
    return actual_count


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _get_last_loaded_date(engine, table: str):
    """Query the most recent transaction_date from a table for incremental loading."""
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text(f"SELECT MAX(transaction_date) FROM {table}")
            )
            row = result.fetchone()
            if row and row[0]:
                logger.info(f"Last loaded date in {table}: {row[0]}")
                return row[0]
    except Exception as e:
        logger.warning(f"Could not query last loaded date from {table}: {e}")
    return None


def verify_load(engine=None) -> dict:
    """
    Verify the loaded data by querying row counts and sample data.

    Returns a dict with verification results.
    """
    if engine is None:
        engine = get_engine()

    results = {}

    with engine.connect() as conn:
        # Sales count
        row = conn.execute(text("SELECT COUNT(*) FROM raw.sales_transactions")).fetchone()
        results["sales_count"] = row[0]

        # Stock count
        row = conn.execute(text("SELECT COUNT(*) FROM raw.stock_inventory")).fetchone()
        results["stock_count"] = row[0]

        # Date range — sales
        row = conn.execute(
            text("SELECT MIN(transaction_date), MAX(transaction_date) FROM raw.sales_transactions")
        ).fetchone()
        results["sales_date_range"] = (str(row[0]), str(row[1])) if row[0] else None

        # Date range — stock
        row = conn.execute(
            text("SELECT MIN(transaction_date), MAX(transaction_date) FROM raw.stock_inventory")
        ).fetchone()
        results["stock_date_range"] = (str(row[0]), str(row[1])) if row[0] else None

        # Unique customers
        row = conn.execute(
            text("SELECT COUNT(DISTINCT customer_name) FROM raw.sales_transactions")
        ).fetchone()
        results["unique_customers"] = row[0]

        # Unique SKUs
        row = conn.execute(
            text("SELECT COUNT(DISTINCT sku) FROM raw.sales_transactions")
        ).fetchone()
        results["unique_skus"] = row[0]

    logger.info("=== Load Verification ===")
    for key, val in results.items():
        logger.info(f"  {key}: {val}")

    return results


def load(
    sales_df: pd.DataFrame,
    stock_df: pd.DataFrame,
    engine=None,
    incremental: bool = False,
) -> dict:
    """
    Main load function — loads both DataFrames into PostgreSQL.

    Returns a dict with row counts.
    """
    if engine is None:
        engine = get_engine()

    logger.info("Starting data loading...")

    sales_count = load_sales(sales_df, engine, incremental)
    stock_count = load_stock(stock_df, engine, incremental)

    logger.info(
        f"Loading complete. Sales: {sales_count:,} rows, Stock: {stock_count:,} rows"
    )

    return {"sales_loaded": sales_count, "stock_loaded": stock_count}


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    from extract import extract
    from transform import transform

    sales_raw, stock_raw = extract()
    sales_clean, stock_clean = transform(sales_raw, stock_raw)

    engine = get_engine()
    result = load(sales_clean, stock_clean, engine, incremental=False)

    print(f"\n{'='*60}")
    print("Load Results:")
    for k, v in result.items():
        print(f"  {k}: {v}")

    print(f"\n{'='*60}")
    print("Verification:")
    verify = verify_load(engine)
    for k, v in verify.items():
        print(f"  {k}: {v}")
