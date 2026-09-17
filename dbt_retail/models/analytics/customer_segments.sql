-- =============================================================
-- customer_segments.sql — Customer RFM & Segmentation View
-- =============================================================
-- Summarizes customer purchasing behavior and tier breakdown.

select
    c.customer_key,
    c.customer_name,
    c.customer_tier,
    c.total_revenue,
    c.total_units_purchased,
    c.total_line_items,
    c.total_active_days,
    c.first_purchase_date,
    c.last_purchase_date,
    c.days_since_last_purchase,
    c.avg_order_line_value,
    dense_rank() over (order by c.total_revenue desc) as customer_revenue_rank

from {{ ref('dim_customer') }} c
order by c.total_revenue desc
