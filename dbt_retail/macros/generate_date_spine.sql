-- =============================================================
-- generate_date_spine.sql
-- =============================================================
-- Macro that generates a series of dates between start_date and
-- end_date (inclusive) at the given datepart granularity.
--
-- Usage:
--   {{ generate_date_spine(
--       datepart   = "day",
--       start_date = "cast('2021-05-01' as date)",
--       end_date   = "cast('2022-06-30' as date)"
--   ) }}
--
-- Returns a CTE-like result with one column: date_day
-- =============================================================

{% macro generate_date_spine(datepart, start_date, end_date) %}

    with date_series as (

        select
            ({{ start_date }} + (n || ' {{ datepart }}')::interval)::date as date_day
        from generate_series(
            0,
            ({{ end_date }} - {{ start_date }})::integer
        ) as t(n)

    )

    select date_day from date_series

{% endmacro %}
