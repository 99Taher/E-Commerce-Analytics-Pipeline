"""
Extract module — Reads the raw CSV and splits it into 3 sections.

The CSV file 'International sale Report.csv' (renamed to retail_sales.csv)
contains 3 concatenated sections:

  Section 1 (rows 0–18,635):  Sales transactions
      Columns: index, DATE, Months, CUSTOMER, Style, SKU, Size, PCS, RATE, GROSS AMT

  Section 2 (rows 18,636–19,675): Product summary (Style + quantity only)
      These rows have data only in the DATE and Months columns (used as Style, Qty)
      → We discard this section entirely.

  Section 3 (rows 19,676–end): Stock/inventory report with re-headered columns
      Header row at line 19,676: index, CUSTOMER, DATE, Months, Style, SKU, PCS, RATE, GROSS AMT, Stock
      → Note: CUSTOMER and DATE are swapped vs Part 1, no Size column, adds Stock column.

This module detects these boundaries and returns two clean DataFrames.
"""

import pandas as pd
from pathlib import Path

from utils import setup_logger, get_csv_path

logger = setup_logger("retail_etl.extract")


# ---------------------------------------------------------------------------
# Section boundary detection
# ---------------------------------------------------------------------------
def _find_section_boundaries(filepath: Path) -> dict:
    """
    Scan the CSV to find where each section starts and ends.

    Returns a dict with keys:
        'part1_end':    last data row index of Part 1 (sales transactions)
        'part2_start':  first row of the product summary section
        'part2_end':    last row of the product summary section
        'part3_header': row index of the Part 3 header
        'part3_start':  first data row of Part 3 (stock/inventory)
    """
    logger.info("Scanning CSV to detect section boundaries...")

    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    total_lines = len(lines)
    logger.info(f"Total lines in CSV: {total_lines}")

    # Part 1 starts at row 1 (row 0 is header)
    # Find where Part 1 ends: look for the product summary section
    # Product summary rows have the pattern: index,StyleName,,,,,,,, or index,SKU,,,,,,,,
    part1_end = None
    part2_start = None
    part3_header = None

    for i, line in enumerate(lines):
        fields = line.strip().split(",")

        # Detect Part 3 header: a line containing "CUSTOMER,DATE,Months,Style,SKU,PCS,RATE,GROSS AMT,Stock"
        if len(fields) >= 10 and fields[1] == "CUSTOMER" and fields[2] == "DATE" and "Stock" in fields[-1]:
            part3_header = i
            logger.info(f"Part 3 header found at line {i}: {line.strip()[:80]}...")
            break

    if part3_header is None:
        raise ValueError("Could not find Part 3 header (Stock report section) in CSV.")

    # Part 1 ends when we hit the product summary section
    # The product summary starts when rows stop having full transaction data
    # Work backwards from the Part 3 header to find where the summary ends
    # and forwards from the end of Part 1 transactions

    # Detect where Part 1 data ends:
    # Part 1 rows have dates like "06-05-21" in column 1 (DATE)
    # Product summary rows have style codes like "SKU" or "JNE3826" in column 1
    for i in range(1, part3_header):
        fields = lines[i].strip().split(",")
        if len(fields) < 10:
            continue
        # Check if the DATE column (fields[1]) looks like a date (contains dashes and numbers)
        date_val = fields[1].strip()
        # Product summary section starts when DATE column is no longer a date
        if date_val and not _looks_like_date(date_val) and date_val != "DATE":
            if part1_end is None:
                part1_end = i - 1
                part2_start = i
                logger.info(f"Part 1 ends at line {part1_end}")
                logger.info(f"Part 2 (product summary) starts at line {part2_start}")
                break

    if part1_end is None:
        part1_end = part3_header - 1
        logger.warning("Could not detect product summary section, assuming Part 1 runs until Part 3 header.")

    boundaries = {
        "part1_end": part1_end,
        "part2_start": part2_start if part2_start else part1_end + 1,
        "part2_end": part3_header - 1,
        "part3_header": part3_header,
        "part3_start": part3_header + 1,
        "total_lines": total_lines,
    }

    logger.info(f"Section boundaries: {boundaries}")
    return boundaries


def _looks_like_date(val: str) -> bool:
    """Check if a string looks like a date in MM-DD-YY format."""
    parts = val.split("-")
    if len(parts) != 3:
        return False
    return all(p.isdigit() for p in parts)


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------
def extract_sales_transactions(filepath: Path | None = None) -> pd.DataFrame:
    """
    Extract Part 1 (sales transactions) from the CSV.

    Returns a DataFrame with columns:
        index, DATE, Months, CUSTOMER, Style, SKU, Size, PCS, RATE, GROSS AMT
    """
    if filepath is None:
        filepath = get_csv_path()

    boundaries = _find_section_boundaries(filepath)

    logger.info("Extracting Part 1: Sales Transactions...")
    # Read only Part 1 rows (header + data up to part1_end)
    nrows = boundaries["part1_end"]  # number of data rows (excluding header)

    df = pd.read_csv(
        filepath,
        nrows=nrows,
        dtype=str,  # Read everything as string first, transform later
        encoding="utf-8",
    )

    logger.info(f"Part 1 extracted: {len(df)} rows × {len(df.columns)} columns")
    logger.debug(f"Part 1 columns: {list(df.columns)}")
    return df


def extract_stock_inventory(filepath: Path | None = None) -> pd.DataFrame:
    """
    Extract Part 3 (stock/inventory report) from the CSV.

    Part 3 has a different header at line 19,676:
        index, CUSTOMER, DATE, Months, Style, SKU, PCS, RATE, GROSS AMT, Stock

    Note: CUSTOMER and DATE are swapped compared to Part 1, there is
    no Size column, and there's an additional Stock column.

    Returns a DataFrame with columns realigned to match Part 1's convention:
        index, DATE, Months, CUSTOMER, Style, SKU, PCS, RATE, GROSS AMT, Stock
    """
    if filepath is None:
        filepath = get_csv_path()

    boundaries = _find_section_boundaries(filepath)

    logger.info("Extracting Part 3: Stock/Inventory Report...")

    # Skip header (row 0) + all Part 1 + Part 2 rows + Part 3 header
    skiprows = boundaries["part3_header"] + 1  # skip everything up to and including Part 3 header

    # Read Part 3 with its own header
    df = pd.read_csv(
        filepath,
        skiprows=range(1, skiprows),  # keep original header (row 0), skip rows 1 to part3_start-1
        dtype=str,
        encoding="utf-8",
    )

    # But that would use Part 1's header. Let's read from the Part 3 header directly.
    # Re-read starting from Part 3's own header line
    df = pd.read_csv(
        filepath,
        header=0,
        skiprows=range(1, boundaries["part3_header"] + 1),  # skip rows 1..part3_header (keep row 0 placeholder)
        dtype=str,
        encoding="utf-8",
    )

    # Actually, simpler approach: read the whole file as lines, extract Part 3 portion
    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # Part 3 header + data
    part3_lines = lines[boundaries["part3_header"]:boundaries["total_lines"]]

    from io import StringIO
    part3_csv = StringIO("".join(part3_lines))

    df = pd.read_csv(part3_csv, dtype=str, encoding="utf-8")

    logger.info(f"Part 3 raw columns: {list(df.columns)}")
    logger.info(f"Part 3 extracted: {len(df)} rows × {len(df.columns)} columns")

    # Realign columns: Part 3 has CUSTOMER, DATE swapped
    # Part 3 header: index, CUSTOMER, DATE, Months, Style, SKU, PCS, RATE, GROSS AMT, Stock
    # We rename to align with Part 1's convention
    df = df.rename(columns={
        "CUSTOMER": "CUSTOMER",
        "DATE": "DATE",
        "Months": "Months",
        "Style": "Style",
        "SKU": "SKU",
        "PCS": "PCS",
        "RATE": "RATE",
        "GROSS AMT": "GROSS AMT",
        "Stock": "Stock",
    })

    # The columns are already named correctly in Part 3's header, but the column
    # ORDER is different. The actual values are correct because pandas reads by header name.
    # So CUSTOMER column in Part 3 truly contains customer names, DATE contains dates, etc.

    return df


def extract(filepath: Path | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Main extraction function — returns (sales_df, stock_df).

    Both DataFrames are raw string-typed data, ready for the transform step.
    """
    if filepath is None:
        filepath = get_csv_path()

    logger.info(f"Starting extraction from: {filepath}")

    sales_df = extract_sales_transactions(filepath)
    stock_df = extract_stock_inventory(filepath)

    logger.info(
        f"Extraction complete. Sales: {len(sales_df)} rows, Stock: {len(stock_df)} rows"
    )

    return sales_df, stock_df


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    sales, stock = extract()
    print(f"\n{'='*60}")
    print(f"Sales Transactions: {len(sales)} rows")
    print(f"Columns: {list(sales.columns)}")
    print(sales.head())
    print(f"\n{'='*60}")
    print(f"Stock Inventory: {len(stock)} rows")
    print(f"Columns: {list(stock.columns)}")
    print(stock.head())
