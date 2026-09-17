-- =============================================================
-- generate_schema_name.sql
-- =============================================================
-- Override default dbt schema naming so that custom schemas
-- (e.g. 'staging', 'warehouse') are used as-is rather than
-- prefixed with the target schema name (e.g. staging_warehouse).
-- =============================================================

{% macro generate_schema_name(custom_schema_name, node) -%}

    {%- set default_schema = target.schema -%}
    {%- if custom_schema_name is none -%}

        {{ default_schema }}

    {%- else -%}

        {{ custom_schema_name | trim }}

    {%- endif -%}

{%- endmacro %}
