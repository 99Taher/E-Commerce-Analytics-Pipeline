"""
Utility helpers for the Retail Sales ETL Pipeline.

Provides:
    - get_engine()      → SQLAlchemy engine connected to retail_dw
    - get_connection()   → raw psycopg2 connection
    - setup_logger()     → configured logger with console + file output
    - log_etl_event()    → write an ETL run event to raw.etl_log
"""

import os
import logging
import uuid
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# ---------------------------------------------------------------------------
# Load environment variables from project root .env
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_ENV_FILE = _PROJECT_ROOT / ".env"

# Also check if running inside Airflow container
if not _ENV_FILE.exists():
    _ENV_FILE = Path("/opt/airflow/.env")

load_dotenv(_ENV_FILE, override=False)


# ---------------------------------------------------------------------------
# Database connection helpers
# ---------------------------------------------------------------------------
def _build_connection_url() -> str:
    """Build the PostgreSQL connection URL from environment variables."""
    # Prefer DATABASE_URL if set directly
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        # Ensure we use the psycopg2 dialect for SQLAlchemy
        if db_url.startswith("postgresql://"):
            db_url = db_url.replace("postgresql://", "postgresql+psycopg2://", 1)
        return db_url

    # Otherwise build from individual vars
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    user = os.getenv("POSTGRES_USER", "retail_user")
    password = os.getenv("POSTGRES_PASSWORD", "retail_pass_2024")
    db = os.getenv("POSTGRES_DB", "retail_dw")
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}"


def get_engine(echo: bool = False):
    """Return a SQLAlchemy engine for the retail data warehouse."""
    url = _build_connection_url()
    return create_engine(url, echo=echo, pool_pre_ping=True)


def get_connection():
    """Return a raw psycopg2 connection (useful for COPY operations)."""
    import psycopg2

    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    user = os.getenv("POSTGRES_USER", "retail_user")
    password = os.getenv("POSTGRES_PASSWORD", "retail_pass_2024")
    db = os.getenv("POSTGRES_DB", "retail_dw")
    return psycopg2.connect(host=host, port=port, user=user, password=password, dbname=db)


# ---------------------------------------------------------------------------
# Logging helpers
# ---------------------------------------------------------------------------
def setup_logger(name: str = "retail_etl", log_dir: str | None = None) -> logging.Logger:
    """
    Configure and return a logger with console + file handlers.

    Args:
        name:    Logger name.
        log_dir: Directory for log files. Defaults to <project_root>/logs/.
    """
    logger = logging.getLogger(name)

    # Avoid adding duplicate handlers on repeated calls
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler (INFO and above)
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(formatter)
    logger.addHandler(console)

    # File handler (DEBUG and above)
    if log_dir is None:
        log_dir = str(_PROJECT_ROOT / "logs")
    Path(log_dir).mkdir(parents=True, exist_ok=True)

    file_handler = logging.FileHandler(
        Path(log_dir) / f"etl_{datetime.now().strftime('%Y%m%d')}.log",
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


# ---------------------------------------------------------------------------
# ETL metadata logging
# ---------------------------------------------------------------------------
def generate_run_id() -> str:
    """Generate a unique run ID for an ETL execution."""
    return f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"


def log_etl_event(
    engine,
    run_id: str,
    step: str,
    status: str,
    rows_processed: int | None = None,
    details: str | None = None,
):
    """
    Write an ETL event to the raw.etl_log table.

    Args:
        engine:          SQLAlchemy engine.
        run_id:          Unique run identifier.
        step:            Pipeline step name (e.g. 'extract', 'transform', 'load').
        status:          'started', 'success', or 'failed'.
        rows_processed:  Number of rows processed (optional).
        details:         Free-text details or error message (optional).
    """
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO raw.etl_log (run_id, step, status, rows_processed, details, completed_at)
                VALUES (:run_id, :step, :status, :rows_processed, :details,
                        CASE WHEN :status IN ('success', 'failed') THEN NOW() ELSE NULL END)
                """
            ),
            {
                "run_id": run_id,
                "step": step,
                "status": status,
                "rows_processed": rows_processed,
                "details": details,
            },
        )


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------
def get_data_dir() -> Path:
    """Return the path to the data/raw/ directory."""
    # Inside Airflow container
    container_path = Path("/opt/airflow/data/raw")
    if container_path.exists():
        return container_path
    # Local development
    return _PROJECT_ROOT / "data" / "raw"


def get_csv_path() -> Path:
    """Return the path to the retail sales CSV file."""
    return get_data_dir() / "retail_sales.csv"
