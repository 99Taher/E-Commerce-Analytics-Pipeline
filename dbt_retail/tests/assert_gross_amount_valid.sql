-- =============================================================
-- assert_gross_amount_valid.sql — Custom singular test
-- =============================================================
-- Validates that gross_amount is positive and logically consistent
-- with quantity * unit_price (i.e. not exceeding the max undiscounted price
-- with reasonable tolerance, and strictly greater than zero).
-- Returns failing rows (dbt singular tests pass when 0 rows returned).

select
    sale_id,
    transaction_id,
    quantity,
    unit_price,
    gross_amount,
    (quantity * unit_price) as undiscounted_amount

from {{ ref('fact_sales') }}

where gross_amount <= 0
   or unit_price <= 0
   or quantity <= 0
   or gross_amount > (quantity * unit_price * 1.5)
