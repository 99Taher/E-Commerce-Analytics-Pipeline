"""
retail_sales_pipeline.py — End-to-End Retail Data Engineering DAG

Orchestrates:
  1. DB Health Check
  2. Raw Data Ingestion (Python ETL: Extract, Transform, Load to PostgreSQL raw schema)
  3. dbt Staging Models (Clean views in staging schema)
  4. dbt Marts Models (Star schema tables in warehouse schema: dim_date, dim_customer, dim_product, fact_sales)
  5. dbt Analytics Models (Analytical views in warehouse schema)
  6. dbt Data Quality & Integrity Tests (schema + custom business rules)
  7. Power BI Data Exports (CSV generation for BI dashboards)
  8. Pipeline Execution Summary Report
"""

import sys
import os
from datetime import datetime, timedelta
from pathlib import Path

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator

# Ensure scripts directory is available in Python path inside Airflow container
SCRIPTS_DIR = "/opt/airflow/scripts"
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)


# ---------------------------------------------------------------------------
# Python Task Callables
# ---------------------------------------------------------------------------
def check_db_connection():
    """Verify PostgreSQL database is accessible."""
    from utils import get_engine
    from sqlalchemy import text

    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1;")).scalar()
        if result != 1:
            raise ConnectionError("Failed to query database!")
    print("✓ PostgreSQL connection check successful.")


def run_raw_etl():
    """Execute Python ETL to load raw data into PostgreSQL."""
    from run_etl import run_pipeline

    results = run_pipeline(incremental=False)
    if results.get("status") != "success":
        raise RuntimeError(f"Raw ETL pipeline failed: {results.get('error')}")
    print(f"✓ Raw ETL loaded {results['load']['sales_loaded']:,} sales rows and {results['load']['stock_loaded']:,} stock rows.")
    return results


def run_bi_exports():
    """Export warehouse tables and views to CSV for Power BI."""
    from export_for_powerbi import run_exports

    summary = run_exports()
    print("✓ Power BI exports generated successfully:", summary)
    return summary


def generate_pipeline_report():
    """Query data warehouse and print full execution stats."""
    from utils import get_engine
    from sqlalchemy import text

    engine = get_engine()
    tables = [
        ("raw", "sales_transactions"),
        ("raw", "stock_inventory"),
        ("warehouse", "dim_date"),
        ("warehouse", "dim_customer"),
        ("warehouse", "dim_product"),
        ("warehouse", "fact_sales"),
        ("warehouse", "monthly_revenue"),
        ("warehouse", "top_products"),
    ]

    print("\n" + "=" * 60)
    print("RETAIL DATA PLATFORM — EXECUTION SUMMARY REPORT")
    print("=" * 60)

    with engine.connect() as conn:
        for schema, tbl in tables:
            try:
                cnt = conn.execute(text(f"SELECT COUNT(*) FROM {schema}.{tbl};")).scalar()
                print(f"  {schema}.{tbl:<28} : {cnt:,} rows")
            except Exception as e:
                print(f"  {schema}.{tbl:<28} : [ERROR] {e}")

        # Summary KPIs
        kpis = conn.execute(text("""
            SELECT
                COUNT(DISTINCT customer_key) as customers,
                SUM(quantity) as total_units,
                SUM(gross_amount) as total_revenue,
                AVG(gross_amount) as avg_order_val
            FROM warehouse.fact_sales;
        """)).fetchone()

        if kpis:
            print("\n--- Key Business Metrics ---")
            print(f"  Total Unique Customers : {kpis[0]:,}")
            print(f"  Total Units Sold       : {kpis[1]:,.0f}")
            print(f"  Total Warehouse Revenue: ${kpis[2]:,.2f}")
            print(f"  Average Order Value    : ${kpis[3]:,.2f}")

    print("=" * 60 + "\n")


# ---------------------------------------------------------------------------
# Default Arguments & DAG Definition
# ---------------------------------------------------------------------------
default_args = {
    "owner": "retail_data_eng",
    "depends_on_past": False,
    "start_date": datetime(2024, 1, 1),
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=1),
}

with DAG(
    dag_id="retail_sales_pipeline",
    default_args=default_args,
    description="End-to-end Retail Sales ETL & dbt dimensional modeling pipeline",
    schedule_interval="@daily",
    catchup=False,
    max_active_runs=1,
    tags=["retail", "etl", "dbt", "warehouse", "powerbi"],
) as dag:

    # Task 1: Check Database Connectivity
    task_check_db = PythonOperator(
        task_id="check_db_connectivity",
        python_callable=check_db_connection,
    )

    # Task 2: Ingest & Load Raw Data
    task_raw_etl = PythonOperator(
        task_id="extract_transform_load_raw",
        python_callable=run_raw_etl,
    )

    # Task 3: dbt Compile & Parse Validation
    task_dbt_compile = BashOperator(
        task_id="dbt_compile",
        bash_command="cd /opt/airflow/dbt_retail && dbt compile --profiles-dir .",
    )

    # Task 4: dbt Staging Models
    task_dbt_staging = BashOperator(
        task_id="dbt_run_staging",
        bash_command="cd /opt/airflow/dbt_retail && dbt run --select staging --profiles-dir .",
    )

    # Task 5: dbt Marts Models (Star Schema)
    task_dbt_marts = BashOperator(
        task_id="dbt_run_marts",
        bash_command="cd /opt/airflow/dbt_retail && dbt run --select marts --profiles-dir .",
    )

    # Task 6: dbt Analytics Views
    task_dbt_analytics = BashOperator(
        task_id="dbt_run_analytics",
        bash_command="cd /opt/airflow/dbt_retail && dbt run --select analytics --profiles-dir .",
    )

    # Task 7: dbt Data Tests
    task_dbt_test = BashOperator(
        task_id="dbt_test_suite",
        bash_command="cd /opt/airflow/dbt_retail && dbt test --profiles-dir .",
    )

    # Task 8: Export Datasets for Power BI
    task_bi_export = PythonOperator(
        task_id="export_for_powerbi",
        python_callable=run_bi_exports,
    )

    # Task 9: Pipeline Summary Report
    task_summary = PythonOperator(
        task_id="generate_pipeline_summary",
        python_callable=generate_pipeline_report,
    )

    # Task Orchestration Flow
    (
        task_check_db
        >> task_raw_etl
        >> task_dbt_compile
        >> task_dbt_staging
        >> task_dbt_marts
        >> task_dbt_analytics
        >> task_dbt_test
        >> task_bi_export
        >> task_summary
    )
