-- =============================================================
-- stg_sales.sql — Staging model for raw sales transactions
-- Source: raw.sales_transactions
-- =============================================================
-- Casts types, standardises column names, filters bad rows,
-- and adds a few derived fields used downstream in the marts.

with source as (

    select * from {{ source('raw', 'sales_transactions') }}

),

cleaned as (

    select
        -- Keys
        id                                          as raw_id,
        md5(concat_ws('|', id::text, coalesce(transaction_date::text, ''), coalesce(customer_name, ''), coalesce(sku, ''))) as transaction_id,

        -- Dates
        transaction_date::date                      as transaction_date,
        to_char(transaction_date, 'YYYY-MM')        as month_key,
        month_year,

        -- Dimensions
        trim(upper(customer_name))                  as customer_name,
        trim(upper(style))                          as style,
        trim(upper(sku))                            as sku,
        trim(upper(size))                           as size,

        -- Measures
        quantity::numeric(10,2)                     as quantity,
        unit_price::numeric(12,2)                   as unit_price,
        gross_amount::numeric(12,2)                 as gross_amount,

        -- Audit
        loaded_at

    from source

    where
        transaction_date is not null
        and customer_name is not null
        and quantity > 0

)

select * from cleaned
