-- =============================================================
-- fact_sales.sql — Central fact table
-- =============================================================
-- One row per sales transaction line item. Contains FK references
-- to dim_date, dim_customer, and dim_product, plus all measures.

with sales as (

    select * from {{ ref('stg_sales') }}

),

dim_date as (

    select date_key, full_date from {{ ref('dim_date') }}

),

dim_customer as (

    select customer_key, customer_name from {{ ref('dim_customer') }}

),

dim_product as (

    select product_key, sku, size from {{ ref('dim_product') }}

),

joined as (

    select
        -- Surrogate key for the fact row
        row_number() over (order by s.transaction_date, s.customer_name, s.sku, s.size)
                                                    as sale_id,

        -- Foreign keys
        d.date_key,
        c.customer_key,
        p.product_key,

        -- Degenerate dimensions (kept on fact for drill-through)
        s.transaction_id,
        s.sku,
        s.size,
        s.style,
        s.month_year,

        -- Measures
        s.quantity,
        s.unit_price,
        s.gross_amount,

        -- Derived measures
        (s.quantity * s.unit_price)::numeric(14,2)  as expected_amount,
        (s.gross_amount - s.quantity * s.unit_price)::numeric(14,2)
                                                    as discount_amount,

        -- Audit
        s.loaded_at,
        s.transaction_date                          as sale_date

    from sales s
    left join dim_date     d on d.full_date     = s.transaction_date
    left join dim_customer c on c.customer_name = s.customer_name
    left join dim_product  p on p.sku = s.sku
                             and p.size = coalesce(s.size, 'UNKNOWN')

)

select * from joined
