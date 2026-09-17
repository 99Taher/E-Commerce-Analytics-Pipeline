-- =============================================================
-- dim_customer.sql — Customer dimension
-- =============================================================
-- One row per unique customer. Includes lifetime value metrics
-- computed directly from the staging sales data.

with customers as (

    select
        customer_name,
        min(transaction_date)               as first_purchase_date,
        max(transaction_date)               as last_purchase_date,
        count(distinct transaction_date)    as total_active_days,
        count(*)                            as total_line_items,
        sum(quantity)                       as total_units_purchased,
        sum(gross_amount)                   as total_revenue,
        avg(gross_amount)                   as avg_order_line_value,

        -- Recency: days since last purchase (relative to max date in dataset)
        (
            select max(transaction_date) from {{ ref('stg_sales') }}
        ) - max(transaction_date)           as days_since_last_purchase

    from {{ ref('stg_sales') }}

    group by customer_name

),

final as (

    select
        -- Surrogate key
        row_number() over (order by customer_name)  as customer_key,

        customer_name,
        first_purchase_date,
        last_purchase_date,
        total_active_days,
        total_line_items,
        total_units_purchased::numeric(12,2)        as total_units_purchased,
        total_revenue::numeric(14,2)                as total_revenue,
        avg_order_line_value::numeric(12,2)         as avg_order_line_value,
        days_since_last_purchase::integer           as days_since_last_purchase,

        -- Customer tier (simple RFM-lite segmentation)
        case
            when total_revenue >= 100000  then 'Platinum'
            when total_revenue >= 50000   then 'Gold'
            when total_revenue >= 10000   then 'Silver'
            else                               'Bronze'
        end                                         as customer_tier

    from customers

)

select * from final
