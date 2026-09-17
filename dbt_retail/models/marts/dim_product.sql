-- =============================================================
-- dim_product.sql — Product dimension (Style + SKU + Size)
-- =============================================================
-- One row per unique SKU. Enriched with style-level and
-- sku-level aggregates from both sales and stock data.

with sales_agg as (

    select
        sku,
        style,
        size,
        count(*)                            as times_sold,
        sum(quantity)                       as total_units_sold,
        sum(gross_amount)                   as total_revenue,
        avg(unit_price)                     as avg_unit_price,
        min(unit_price)                     as min_unit_price,
        max(unit_price)                     as max_unit_price,
        min(transaction_date)               as first_sale_date,
        max(transaction_date)               as last_sale_date

    from {{ ref('stg_sales') }}

    where sku is not null

    group by sku, style, size

),

stock_agg as (

    select
        sku,
        sum(stock_level)                    as total_stock,
        avg(stock_level)                    as avg_stock_level,
        max(stock_level)                    as max_stock_level

    from {{ ref('stg_stock') }}

    where sku is not null

    group by sku

),

final as (

    select
        -- Surrogate key
        row_number() over (order by s.style, s.sku, s.size)    as product_key,

        s.sku,
        s.style,
        coalesce(s.size, 'UNKNOWN')                             as size,

        -- Sales metrics
        s.times_sold,
        s.total_units_sold::numeric(12,2)                       as total_units_sold,
        s.total_revenue::numeric(14,2)                          as total_revenue,
        s.avg_unit_price::numeric(12,2)                         as avg_unit_price,
        s.min_unit_price::numeric(12,2)                         as min_unit_price,
        s.max_unit_price::numeric(12,2)                         as max_unit_price,
        s.first_sale_date,
        s.last_sale_date,

        -- Stock metrics (may be null if no stock record)
        coalesce(st.total_stock, 0)::integer                    as total_stock,
        coalesce(st.avg_stock_level, 0)::numeric(10,2)          as avg_stock_level,
        coalesce(st.max_stock_level, 0)::integer                as max_stock_level,

        -- Derived
        case
            when coalesce(st.total_stock, 0) = 0 then 'Out of Stock'
            when coalesce(st.total_stock, 0) < 5  then 'Low Stock'
            else 'In Stock'
        end                                                     as stock_status

    from sales_agg s
    left join stock_agg st using (sku)

)

select * from final
