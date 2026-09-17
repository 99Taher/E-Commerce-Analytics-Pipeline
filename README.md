# Retail Sales Data Engineering & Analytics Platform

An end-to-end modern data engineering platform that extracts, cleans, transforms, models, tests, and orchestrates retail sales transactions and inventory datasets using **Python**, **PostgreSQL**, **dbt**, **Apache Airflow**, and **Docker**.

---

## 🏛️ Architecture Overview

```mermaid
flowchart TD
    subgraph Ingestion ["1. INGESTION LAYER"]
        CSV["📄 Raw CSV Reports<br/>(37,434 rows, 3 sections)"]
        PyETL["🐍 Python ETL Pipeline<br/>(extract.py, transform.py, load.py)"]
        CSV --> PyETL
    end

    subgraph Storage ["2. POSTGRESQL DATA WAREHOUSE"]
        RawDB[("raw.sales_transactions<br/>raw.stock_inventory<br/>raw.etl_log")]
        StagingDB[("staging.stg_sales<br/>staging.stg_stock")]
        WarehouseDB[("warehouse.dim_date<br/>warehouse.dim_customer<br/>warehouse.dim_product<br/>warehouse.fact_sales")]
        AnalyticsDB[("warehouse.monthly_revenue<br/>warehouse.top_products<br/>warehouse.customer_segments<br/>warehouse.size_distribution<br/>warehouse.daily_sales_trend")]
    end

    subgraph Transformation ["3. TRANSFORMATION & MODELING (dbt)"]
        dbtStg["dbt Staging Views"]
        dbtMarts["dbt Dimensional Marts (Star Schema)"]
        dbtAnalytics["dbt Analytics Views"]
        dbtTests["dbt Data Quality & Integrity Tests (48+ tests)"]
    end

    subgraph Orchestration ["4. ORCHESTRATION (Apache Airflow)"]
        DAG["🌀 retail_sales_pipeline DAG<br/>(@daily schedule / LocalExecutor)"]
    end

    subgraph Consumption ["5. CONSUMPTION & BI"]
        PBI["📊 Power BI Dashboards & CSV Exports"]
    end

    PyETL --> RawDB
    RawDB --> dbtStg --> StagingDB
    StagingDB --> dbtMarts --> WarehouseDB
    WarehouseDB --> dbtAnalytics --> AnalyticsDB
    AnalyticsDB 
---


---


