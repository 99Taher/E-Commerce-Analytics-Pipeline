"""
run_etl.py — Main entry point for the Retail Sales ETL Pipeline.

Usage:
    python scripts/run_etl.py                 # Full load (truncate + insert)
    python scripts/run_etl.py --incremental   # Incremental load (append new rows only)
    python scripts/run_etl.py --verify-only   # Just verify existing data, no loading

The pipeline runs 3 steps:
    1. EXTRACT  — Read CSV, split into sales + stock sections
    2. TRANSFORM — Clean, validate, standardize
    3. LOAD     — Insert into PostgreSQL raw schema tables
"""

import sys
import argparse
import traceback
from datetime import datetime

from utils import setup_logger, get_engine, generate_run_id, log_etl_event
from extract import extract
from transform import transform
from load import load, verify_load

logger = setup_logger("retail_etl")


def run_pipeline(incremental: bool = False) -> dict:
    """
    Execute the full ETL pipeline.

    Args:
        incremental: If True, only load new rows since the last run.

    Returns:
        Dictionary with pipeline results and metadata.
    """
    engine = get_engine()
    run_id = generate_run_id()
    start_time = datetime.now()

    results = {
        "run_id": run_id,
        "mode": "incremental" if incremental else "full",
        "started_at": start_time.isoformat(),
        "status": "started",
    }

    logger.info("=" * 60)
    logger.info(f"RETAIL SALES ETL PIPELINE — {results['mode'].upper()} LOAD")
    logger.info(f"Run ID: {run_id}")
    logger.info(f"Started: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)

    try:
        # --- Step 1: EXTRACT ---
        logger.info("\n" + "─" * 40)
        logger.info("STEP 1/3: EXTRACT")
        logger.info("─" * 40)
        log_etl_event(engine, run_id, "extract", "started")

        sales_raw, stock_raw = extract()

        log_etl_event(
            engine, run_id, "extract", "success",
            rows_processed=len(sales_raw) + len(stock_raw),
            details=f"Sales: {len(sales_raw)} rows, Stock: {len(stock_raw)} rows",
        )

        # --- Step 2: TRANSFORM ---
        logger.info("\n" + "─" * 40)
        logger.info("STEP 2/3: TRANSFORM")
        logger.info("─" * 40)
        log_etl_event(engine, run_id, "transform", "started")

        sales_clean, stock_clean = transform(sales_raw, stock_raw)

        log_etl_event(
            engine, run_id, "transform", "success",
            rows_processed=len(sales_clean) + len(stock_clean),
            details=f"Sales: {len(sales_clean)} rows, Stock: {len(stock_clean)} rows",
        )

        # --- Step 3: LOAD ---
        logger.info("\n" + "─" * 40)
        logger.info("STEP 3/3: LOAD")
        logger.info("─" * 40)
        log_etl_event(engine, run_id, "load", "started")

        load_results = load(sales_clean, stock_clean, engine, incremental=incremental)

        log_etl_event(
            engine, run_id, "load", "success",
            rows_processed=load_results["sales_loaded"] + load_results["stock_loaded"],
            details=f"Sales: {load_results['sales_loaded']} rows, Stock: {load_results['stock_loaded']} rows",
        )

        # --- Verification ---
        logger.info("\n" + "─" * 40)
        logger.info("VERIFICATION")
        logger.info("─" * 40)
        verification = verify_load(engine)

        # --- Final summary ---
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        results.update({
            "status": "success",
            "completed_at": end_time.isoformat(),
            "duration_seconds": round(duration, 2),
            "extract": {"sales_raw": len(sales_raw), "stock_raw": len(stock_raw)},
            "transform": {"sales_clean": len(sales_clean), "stock_clean": len(stock_clean)},
            "load": load_results,
            "verification": verification,
        })

        log_etl_event(
            engine, run_id, "pipeline", "success",
            rows_processed=load_results["sales_loaded"] + load_results["stock_loaded"],
            details=f"Pipeline completed in {duration:.1f}s",
        )

        logger.info("\n" + "=" * 60)
        logger.info("PIPELINE COMPLETED SUCCESSFULLY")
        logger.info(f"Duration: {duration:.1f}s")
        logger.info(f"Sales loaded:  {load_results['sales_loaded']:,} rows")
        logger.info(f"Stock loaded:  {load_results['stock_loaded']:,} rows")
        logger.info("=" * 60)

    except Exception as e:
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        results.update({
            "status": "failed",
            "completed_at": end_time.isoformat(),
            "duration_seconds": round(duration, 2),
            "error": str(e),
        })

        logger.error(f"PIPELINE FAILED: {e}")
        logger.error(traceback.format_exc())

        try:
            log_etl_event(
                engine, run_id, "pipeline", "failed",
                details=f"Error: {str(e)[:500]}",
            )
        except Exception:
            pass  # Don't let logging failure mask the real error

        raise

    return results


def main():
    """CLI entry point with argument parsing."""
    parser = argparse.ArgumentParser(
        description="Retail Sales ETL Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python scripts/run_etl.py                 # Full load
    python scripts/run_etl.py --incremental   # Incremental load
    python scripts/run_etl.py --verify-only   # Verify existing data
        """,
    )

    parser.add_argument(
        "--incremental",
        action="store_true",
        help="Run in incremental mode (only load new rows since last run)",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Only verify existing data, do not run the pipeline",
    )

    args = parser.parse_args()

    if args.verify_only:
        logger.info("Running verification only...")
        engine = get_engine()
        results = verify_load(engine)
        print("\nVerification Results:")
        for k, v in results.items():
            print(f"  {k}: {v}")
        return

    try:
        results = run_pipeline(incremental=args.incremental)
        print(f"\nPipeline finished: {results['status']}")
        sys.exit(0)
    except Exception:
        sys.exit(1)


if __name__ == "__main__":
    main()
