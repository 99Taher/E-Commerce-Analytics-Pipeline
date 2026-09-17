-- =============================================================
-- dim_date.sql — Date dimension (calendar table)
-- =============================================================
-- Generates one row per calendar day covering the full range
-- of dates present in the sales data (Jun 2021 – May 2022),
-- plus a 30-day buffer on each side.

with date_spine as (

    {{ generate_date_spine(
        datepart   = "day",
        start_date = "cast('2010-01-01' as date)",
        end_date   = "cast('2030-12-31' as date)"
    ) }}

),

final as (

    select
        -- Surrogate key: integer YYYYMMDD (e.g. 20210605)
        cast(to_char(date_day, 'YYYYMMDD') as integer)  as date_key,
        date_day                                         as full_date,

        -- Year / Quarter / Month
        extract(year  from date_day)::integer            as year,
        extract(quarter from date_day)::integer          as quarter,
        extract(month from date_day)::integer            as month_num,
        to_char(date_day, 'Month')                       as month_name,
        to_char(date_day, 'Mon')                         as month_short,
        to_char(date_day, 'YYYY-MM')                     as year_month,

        -- Week / Day
        extract(week from date_day)::integer             as week_of_year,
        extract(dow  from date_day)::integer             as day_of_week,   -- 0=Sun
        to_char(date_day, 'Day')                         as day_name,
        to_char(date_day, 'Dy')                          as day_short,
        extract(day  from date_day)::integer             as day_of_month,
        extract(doy  from date_day)::integer             as day_of_year,

        -- Flags
        case when extract(dow from date_day) in (0, 6)
             then true else false end                    as is_weekend,
        case when extract(dow from date_day) not in (0, 6)
             then true else false end                    as is_weekday,

        -- Fiscal helpers (simple: fiscal year = calendar year)
        extract(year from date_day)::integer             as fiscal_year,
        extract(quarter from date_day)::integer          as fiscal_quarter

    from date_spine

)

select * from final
order by date_key
