-- =============================================================
-- monthly_revenue.sql — Monthly Sales Performance Mart View
-- =============================================================
-- Aggregates revenue, order count, units sold, and computes
-- Month-over-Month (MoM) growth percentage.

with monthly as (

    select
        d.year,
        d.month_num,
        d.year_month,
        d.month_name,
        count(distinct f.sale_id)                   as total_transactions,
        count(distinct f.customer_key)              as active_customers,
        sum(f.quantity)                             as total_units_sold,
        sum(f.gross_amount)                         as total_revenue,
        avg(f.gross_amount)                         as avg_transaction_value

    from {{ ref('fact_sales') }} f
    join {{ ref('dim_date') }}   d on d.date_key = f.date_key

    group by d.year, d.month_num, d.year_month, d.month_name

),

with_mom as (

    select
        year,
        month_num,
        year_month,
        trim(month_name)                            as month_name,
        total_transactions,
        active_customers,
        total_units_sold::numeric(12,2)             as total_units_sold,
        total_revenue::numeric(14,2)                as total_revenue,
        avg_transaction_value::numeric(12,2)        as avg_transaction_value,

        -- Previous month revenue for MoM calculation
        lag(total_revenue) over (order by year, month_num) as prev_month_revenue,

        -- MoM Revenue Growth %
        round(
            (
                (total_revenue - lag(total_revenue) over (order by year, month_num))
                / nullif(lag(total_revenue) over (order by year, month_num), 0)
            ) * 100.0,
            2
        )                                           as mom_growth_pct

    from monthly

)

select * from with_mom
order by year, month_num
