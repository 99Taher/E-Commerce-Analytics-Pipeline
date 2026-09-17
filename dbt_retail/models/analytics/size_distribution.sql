-- =============================================================
-- size_distribution.sql — Sales breakdown by apparel size
-- =============================================================

with total_sales as (

    select
        sum(gross_amount) as grand_total_revenue,
        sum(quantity)     as grand_total_units
    from {{ ref('fact_sales') }}

),

by_size as (

    select
        coalesce(s.size, 'UNKNOWN')                 as size,
        count(*)                                    as transaction_count,
        sum(s.quantity)                             as total_units_sold,
        sum(s.gross_amount)                         as total_revenue,
        avg(s.unit_price)                           as avg_unit_price

    from {{ ref('fact_sales') }} s
    group by coalesce(s.size, 'UNKNOWN')

)

select
    b.size,
    b.transaction_count,
    b.total_units_sold::numeric(12,2)               as total_units_sold,
    b.total_revenue::numeric(14,2)                  as total_revenue,
    b.avg_unit_price::numeric(12,2)                 as avg_unit_price,
    round((b.total_revenue / t.grand_total_revenue * 100.0), 2) as pct_of_revenue,
    round((b.total_units_sold / t.grand_total_units * 100.0), 2) as pct_of_units

from by_size b
cross join total_sales t
order by b.total_revenue desc
