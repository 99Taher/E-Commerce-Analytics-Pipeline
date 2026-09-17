"""
export_for_powerbi.py — Export data warehouse tables and analytics views to CSV for Power BI.

Usage:
    python scripts/export_for_powerbi.py

Outputs CSV files to `powerbi/exports/`:
    - monthly_revenue.csv
    - top_products.csv
    - customer_segments.csv
    - size_distribution.csv
    - daily_sales_trend.csv
    - dim_date.csv
    - dim_customer.csv
    - dim_product.csv
    - fact_sales.csv
"""

import sys
import os
from pathlib import Path
import pandas as pd
from sqlalchemy import text

# Add scripts directory to path
_SCRIPTS_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPTS_DIR.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from utils import setup_logger, get_engine

logger = setup_logger("retail_etl.export")


def get_export_dir() -> Path:
    """Return the destination path for Power BI CSV exports."""
    # Check container vs local
    container_path = Path("/opt/airflow/powerbi/exports")
    if Path("/opt/airflow").exists():
        container_path.mkdir(parents=True, exist_ok=True)
        return container_path

    local_path = _PROJECT_ROOT / "powerbi" / "exports"
    local_path.mkdir(parents=True, exist_ok=True)
    return local_path


def export_table_or_view(engine, schema: str, name: str, output_dir: Path) -> int:
    """Export a PostgreSQL table or view to a CSV file."""
    query = f"SELECT * FROM {schema}.{name}"
    logger.info(f"Exporting {schema}.{name}...")

    df = pd.read_sql_query(text(query), con=engine.connect())
    out_file = output_dir / f"{name}.csv"
    df.to_csv(out_file, index=False, encoding="utf-8")

    logger.info(f"✓ Saved {len(df):,} rows to {out_file.name}")
    return len(df)


def run_exports() -> dict:
    """Run all Power BI dataset exports."""
    engine = get_engine()
    export_dir = get_export_dir()

    logger.info("=" * 60)
    logger.info("POWER BI DATA EXPORT STARTING")
    logger.info(f"Target Directory: {export_dir}")
    logger.info("=" * 60)

    exports = [
        ("warehouse", "monthly_revenue"),
        ("warehouse", "top_products"),
        ("warehouse", "customer_segments"),
        ("warehouse", "size_distribution"),
        ("warehouse", "daily_sales_trend"),
        ("warehouse", "dim_date"),
        ("warehouse", "dim_customer"),
        ("warehouse", "dim_product"),
        ("warehouse", "fact_sales"),
    ]

    summary = {}
    for schema, name in exports:
        try:
            row_count = export_table_or_view(engine, schema, name, export_dir)
            summary[name] = {"status": "success", "rows": row_count}
        except Exception as e:
            logger.error(f"Failed to export {schema}.{name}: {e}")
            summary[name] = {"status": "failed", "error": str(e)}

    logger.info("=" * 60)
    logger.info("POWER BI DATA EXPORT COMPLETED")
    for name, res in summary.items():
        if res["status"] == "success":
            logger.info(f"  ✓ {name:25} : {res['rows']:,} rows")
        else:
            logger.info(f"  ✗ {name:25} : FAILED ({res.get('error')})")
    logger.info("=" * 60)

    return summary


if __name__ == "__main__":
    run_exports()
