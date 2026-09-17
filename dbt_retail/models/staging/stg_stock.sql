-- =============================================================
-- stg_stock.sql — Staging model for raw stock/inventory data
-- Source: raw.stock_inventory
-- =============================================================

with source as (

    select * from {{ source('raw', 'stock_inventory') }}

),

cleaned as (

    select
        -- Keys
        id                                          as raw_id,

        -- Dates
        transaction_date::date                      as transaction_date,
        to_char(transaction_date, 'YYYY-MM')        as month_key,
        month_year,

        -- Dimensions
        trim(upper(customer_name))                  as customer_name,
        trim(upper(style))                          as style,
        trim(upper(sku))                            as sku,

        -- Measures
        quantity::numeric(10,2)                     as quantity,
        unit_price::numeric(12,2)                   as unit_price,
        gross_amount::numeric(12,2)                 as gross_amount,
        stock::integer                              as stock_level,

        -- Audit
        loaded_at

    from source

    where
        transaction_date is not null
        and customer_name is not null

)

select * from cleaned
