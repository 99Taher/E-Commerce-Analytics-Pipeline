-- =============================================================
-- top_products.sql — Product Sales & Inventory Ranking View
-- =============================================================
-- Ranks products by revenue and units sold, joined with stock status.

with ranked_products as (

    select
        p.product_key,
        p.sku,
        p.style,
        p.size,
        p.times_sold,
        p.total_units_sold,
        p.total_revenue,
        p.avg_unit_price,
        p.total_stock,
        p.stock_status,
        dense_rank() over (order by p.total_revenue desc) as revenue_rank,
        dense_rank() over (order by p.total_units_sold desc) as units_rank

    from {{ ref('dim_product') }} p
    where p.times_sold > 0

)

select * from ranked_products
order by revenue_rank
