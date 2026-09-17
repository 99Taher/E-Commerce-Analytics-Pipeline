"""
Transform module — Cleans, validates, and standardizes extracted data.

Transformations applied:
    1. Parse dates from MM-DD-YY → YYYY-MM-DD
    2. Normalize size values (uppercase, map variants)
    3. Cast numeric columns (PCS, RATE, GROSS AMT, Stock)
    4. Handle nulls (drop rows missing critical fields, fill SKU from Style+Size)
    5. Remove duplicates based on business key
    6. Generate surrogate transaction_id
    7. Trim whitespace from all string columns
    8. Validate data integrity (gross_amount ≈ quantity × unit_price)
"""

import hashlib
import pandas as pd
import numpy as np

from utils import setup_logger

logger = setup_logger("retail_etl.transform")

# ---------------------------------------------------------------------------
# Size normalization mapping
# ---------------------------------------------------------------------------
SIZE_MAPPING = {
    "s": "S",
    "m": "M",
    "l": "L",
    "xl": "XL",
    "xxl": "XXL",
    "xxxl": "XXXL",
    "4xl": "4XL",
    "5xl": "5XL",
    "free": "FREE",
    "Free": "FREE",
    "FREE": "FREE",
    "pcs": "PCS",
    "Pcs": "PCS",
    "PCS": "PCS",
}


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------
def _trim_strings(df: pd.DataFrame) -> pd.DataFrame:
    """Strip leading/trailing whitespace from all string columns."""
    str_cols = df.select_dtypes(include=["object"]).columns
    for col in str_cols:
        df[col] = df[col].str.strip()
    return df


def _parse_dates(series: pd.Series) -> pd.Series:
    """
    Parse dates from MM-DD-YY format to datetime.

    Handles edge cases:
        - NaN/empty values → NaT
        - Invalid dates → NaT (logged as warnings)
    """
    # Replace empty strings with NaN
    series = series.replace("", np.nan)

    parsed = pd.to_datetime(series, format="%m-%d-%y", errors="coerce")

    invalid_count = parsed.isna().sum() - series.isna().sum()
    if invalid_count > 0:
        logger.warning(f"  {invalid_count} dates could not be parsed and were set to NaT")

    return parsed


def _normalize_sizes(series: pd.Series) -> pd.Series:
    """Normalize size values to uppercase standard forms."""
    # Strip and uppercase
    normalized = series.str.strip()

    # Apply mapping
    normalized = normalized.map(lambda x: SIZE_MAPPING.get(x, x) if pd.notna(x) else x)

    return normalized


def _cast_numeric(series: pd.Series, col_name: str, as_int: bool = False) -> pd.Series:
    """
    Cast a string series to numeric, handling commas and errors.

    Args:
        series:   The pandas Series to cast.
        col_name: Column name (for logging).
        as_int:   If True, cast to Int64 (nullable integer).
    """
    # Remove commas from numbers (e.g., "1,275.00")
    cleaned = series.str.replace(",", "", regex=False) if series.dtype == object else series

    numeric = pd.to_numeric(cleaned, errors="coerce")

    invalid_count = numeric.isna().sum() - series.isna().sum()
    if invalid_count > 0:
        logger.warning(f"  {col_name}: {invalid_count} values could not be converted to numeric")

    if as_int:
        numeric = numeric.astype("Int64")  # nullable integer

    return numeric


def _generate_transaction_id(row: pd.Series) -> str:
    """Generate a deterministic surrogate key from business key fields."""
    key = f"{row.get('transaction_date', '')}|{row.get('customer_name', '')}|{row.get('sku', '')}|{row.get('size', '')}|{row.get('quantity', '')}|{row.get('unit_price', '')}"
    return hashlib.md5(key.encode()).hexdigest()[:16]


def _fill_missing_sku(df: pd.DataFrame) -> pd.DataFrame:
    """Fill missing SKU values from Style + Size when possible."""
    missing_sku = df["sku"].isna() | (df["sku"] == "")

    if missing_sku.sum() > 0:
        logger.info(f"  Filling {missing_sku.sum()} missing SKU values from Style+Size")

        # Build SKU from Style-KR-Size pattern (observed in data)
        df.loc[missing_sku, "sku"] = (
            df.loc[missing_sku, "style"].fillna("")
            + "-KR-"
            + df.loc[missing_sku, "size"].fillna("")
        )

        # If style is also missing, leave as NaN
        still_missing = df["sku"].str.startswith("-KR-") | df["sku"].str.endswith("-KR-")
        df.loc[still_missing, "sku"] = np.nan

    return df


# ---------------------------------------------------------------------------
# Main transform functions
# ---------------------------------------------------------------------------
def transform_sales(df: pd.DataFrame) -> pd.DataFrame:
    """
    Transform raw sales transactions DataFrame.

    Input columns:  index, DATE, Months, CUSTOMER, Style, SKU, Size, PCS, RATE, GROSS AMT
    Output columns: transaction_date, month_year, customer_name, style, sku, size,
                    quantity, unit_price, gross_amount
    """
    logger.info(f"Transforming sales data: {len(df)} rows")

    # Work on a copy
    df = df.copy()

    # Step 1: Drop the index column (it's just the CSV row number)
    if "index" in df.columns:
        df = df.drop(columns=["index"])

    # Step 2: Rename columns to snake_case
    df = df.rename(columns={
        "DATE": "transaction_date",
        "Months": "month_year",
        "CUSTOMER": "customer_name",
        "Style": "style",
        "SKU": "sku",
        "Size": "size",
        "PCS": "quantity",
        "RATE": "unit_price",
        "GROSS AMT": "gross_amount",
    })

    # Step 3: Trim whitespace
    logger.info("  Trimming whitespace...")
    df = _trim_strings(df)

    # Step 4: Parse dates
    logger.info("  Parsing dates (MM-DD-YY → datetime)...")
    df["transaction_date"] = _parse_dates(df["transaction_date"])

    # Step 5: Normalize sizes
    logger.info("  Normalizing sizes...")
    df["size"] = _normalize_sizes(df["size"])

    # Step 6: Cast numeric columns
    logger.info("  Casting numeric columns...")
    df["quantity"] = _cast_numeric(df["quantity"], "quantity")
    df["unit_price"] = _cast_numeric(df["unit_price"], "unit_price")
    df["gross_amount"] = _cast_numeric(df["gross_amount"], "gross_amount")

    # Step 7: Fill missing SKUs
    logger.info("  Filling missing SKUs...")
    df = _fill_missing_sku(df)

    # Step 8: Drop rows missing critical fields
    before = len(df)
    df = df.dropna(subset=["transaction_date", "customer_name"])
    dropped = before - len(df)
    if dropped > 0:
        logger.warning(f"  Dropped {dropped} rows with missing date or customer")

    # Step 9: Remove duplicates based on business key
    before = len(df)
    df = df.drop_duplicates(
        subset=["transaction_date", "customer_name", "sku", "size"],
        keep="first",
    )
    deduped = before - len(df)
    if deduped > 0:
        logger.info(f"  Removed {deduped} duplicate rows (by date+customer+sku+size)")

    # Step 10: Generate surrogate transaction IDs
    logger.info("  Generating transaction IDs...")
    df["transaction_id"] = df.apply(_generate_transaction_id, axis=1)

    # Step 11: Validate gross_amount ≈ quantity × unit_price
    _validate_amounts(df)

    # Step 12: Reset index
    df = df.reset_index(drop=True)

    logger.info(f"Sales transform complete: {len(df)} clean rows")
    return df


def transform_stock(df: pd.DataFrame) -> pd.DataFrame:
    """
    Transform raw stock/inventory DataFrame.

    Input columns (Part 3): index, CUSTOMER, DATE, Months, Style, SKU, PCS, RATE, GROSS AMT, Stock
    Output columns: transaction_date, month_year, customer_name, style, sku,
                    quantity, unit_price, gross_amount, stock
    """
    logger.info(f"Transforming stock data: {len(df)} rows")

    # Work on a copy
    df = df.copy()

    # Step 1: Drop the index column
    # Part 3's first column is the row index from the original CSV
    first_col = df.columns[0]
    if first_col.isdigit() or first_col == "index" or first_col.strip().isdigit():
        df = df.drop(columns=[first_col])
    elif "index" in df.columns:
        df = df.drop(columns=["index"])
    # Also check if the first column is a numeric index column with a different name
    elif df.iloc[:, 0].str.strip().str.isdigit().all():
        df = df.drop(columns=[df.columns[0]])

    # Step 2: Rename columns to snake_case
    # Part 3 header: CUSTOMER, DATE, Months, Style, SKU, PCS, RATE, GROSS AMT, Stock
    df = df.rename(columns={
        "CUSTOMER": "customer_name",
        "DATE": "transaction_date",
        "Months": "month_year",
        "Style": "style",
        "SKU": "sku",
        "PCS": "quantity",
        "RATE": "unit_price",
        "GROSS AMT": "gross_amount",
        "Stock": "stock",
    })

    # Step 3: Trim whitespace
    logger.info("  Trimming whitespace...")
    df = _trim_strings(df)

    # Step 4: Parse dates
    logger.info("  Parsing dates (MM-DD-YY → datetime)...")
    df["transaction_date"] = _parse_dates(df["transaction_date"])

    # Step 5: Cast numeric columns
    logger.info("  Casting numeric columns...")
    df["quantity"] = _cast_numeric(df["quantity"], "quantity")
    df["unit_price"] = _cast_numeric(df["unit_price"], "unit_price")
    df["gross_amount"] = _cast_numeric(df["gross_amount"], "gross_amount")
    df["stock"] = _cast_numeric(df["stock"], "stock", as_int=True)

    # Step 6: Drop rows missing critical fields
    before = len(df)
    df = df.dropna(subset=["transaction_date", "customer_name"])
    dropped = before - len(df)
    if dropped > 0:
        logger.warning(f"  Dropped {dropped} rows with missing date or customer")

    # Step 7: Remove duplicates based on business key (no size in stock data)
    before = len(df)
    df = df.drop_duplicates(
        subset=["transaction_date", "customer_name", "sku"],
        keep="first",
    )
    deduped = before - len(df)
    if deduped > 0:
        logger.info(f"  Removed {deduped} duplicate rows (by date+customer+sku)")

    # Step 8: Validate gross_amount ≈ quantity × unit_price
    _validate_amounts(df)

    # Step 9: Reset index
    df = df.reset_index(drop=True)

    logger.info(f"Stock transform complete: {len(df)} clean rows")
    return df


def _validate_amounts(df: pd.DataFrame) -> None:
    """Log a warning if gross_amount diverges significantly from quantity × unit_price."""
    expected = df["quantity"] * df["unit_price"]
    diff = (df["gross_amount"] - expected).abs()
    tolerance = 1.0  # Allow $1 rounding difference

    mismatches = diff > tolerance
    mismatch_count = mismatches.sum()

    if mismatch_count > 0:
        pct = (mismatch_count / len(df)) * 100
        logger.warning(
            f"  Amount validation: {mismatch_count} rows ({pct:.1f}%) have "
            f"gross_amount ≠ quantity × unit_price (tolerance: ±${tolerance:.2f})"
        )
    else:
        logger.info("  Amount validation: all rows pass (gross_amount ≈ quantity × unit_price)")


def transform(
    sales_df: pd.DataFrame, stock_df: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Main transform function — cleans both DataFrames.

    Returns (clean_sales_df, clean_stock_df).
    """
    logger.info("Starting data transformation...")

    clean_sales = transform_sales(sales_df)
    clean_stock = transform_stock(stock_df)

    logger.info(
        f"Transformation complete. "
        f"Sales: {len(clean_sales)} rows, Stock: {len(clean_stock)} rows"
    )

    return clean_sales, clean_stock


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    from extract import extract

    sales_raw, stock_raw = extract()
    sales_clean, stock_clean = transform(sales_raw, stock_raw)

    print(f"\n{'='*60}")
    print("Clean Sales Transactions:")
    print(f"  Rows:    {len(sales_clean)}")
    print(f"  Columns: {list(sales_clean.columns)}")
    print(f"  Dtypes:\n{sales_clean.dtypes}")
    print(sales_clean.head())

    print(f"\n{'='*60}")
    print("Clean Stock Inventory:")
    print(f"  Rows:    {len(stock_clean)}")
    print(f"  Columns: {list(stock_clean.columns)}")
    print(f"  Dtypes:\n{stock_clean.dtypes}")
    print(stock_clean.head())
