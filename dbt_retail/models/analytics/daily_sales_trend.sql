-- =============================================================
-- daily_sales_trend.sql — Daily revenue with 7-day moving average
-- =============================================================

with daily_aggregates as (

    select
        d.full_date                                 as sale_date,
        d.date_key,
        d.day_name,
        d.is_weekend,
        count(distinct f.sale_id)                   as daily_transactions,
        coalesce(sum(f.quantity), 0)                as daily_units,
        coalesce(sum(f.gross_amount), 0)            as daily_revenue

    from {{ ref('dim_date') }} d
    left join {{ ref('fact_sales') }} f on f.date_key = d.date_key

    where d.full_date between '2021-06-01' and '2022-04-30'

    group by d.full_date, d.date_key, d.day_name, d.is_weekend

)

select
    sale_date,
    date_key,
    trim(day_name)                                  as day_name,
    is_weekend,
    daily_transactions,
    daily_units::numeric(10,2)                      as daily_units,
    daily_revenue::numeric(14,2)                    as daily_revenue,
    round(
        avg(daily_revenue) over (
            order by sale_date
            rows between 6 preceding and current row
        ),
        2
    )::numeric(14,2)                                as moving_avg_7d_revenue

from daily_aggregates
order by sale_date
