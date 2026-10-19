{#-
  Generic data tests for the evaluation framework.

  Every test returns one row per violation with a common evidence schema so that
  stored failures can be unioned into a single exception table:

    rule_id            varchar  contract rule identifier
    _scenario_id       varchar  batch / scenario identifier (several scenarios can be tested in one run)
    _row_id            bigint   stable record identifier assigned at ingestion
    implicated_columns varchar  comma-separated columns referenced by the rule
    observed           varchar  observed value(s) of the implicated expression
    expected           varchar  human-readable expectation

  Column names are passed pre-quoted by the generator (they may contain dots).
-#}

{% test dq_not_null(model, rule_id, column_sql, column_name_text) %}
select '{{ rule_id }}' as rule_id, _scenario_id, _row_id,
       '{{ column_name_text }}' as implicated_columns,
       'NULL' as observed,
       'not null' as expected
from {{ model }}
where {{ column_sql }} is null
{% endtest %}


{% test dq_unique(model, rule_id, column_sql, column_name_text) %}
with counted as (
    select _scenario_id, _row_id, {{ column_sql }} as v,
           count(*) over (partition by _scenario_id, {{ column_sql }}) as n
    from {{ model }}
)
select '{{ rule_id }}' as rule_id, _scenario_id, _row_id,
       '{{ column_name_text }}' as implicated_columns,
       cast(v as varchar) as observed,
       'unique (found ' || cast(n as varchar) || ' rows)' as expected
from counted
where n > 1 and v is not null
{% endtest %}


{% test dq_accepted_values(model, rule_id, column_sql, column_name_text, values_sql) %}
select '{{ rule_id }}' as rule_id, _scenario_id, _row_id,
       '{{ column_name_text }}' as implicated_columns,
       cast({{ column_sql }} as varchar) as observed,
       'in ({{ values_sql | replace("'", "") }})' as expected
from {{ model }}
where {{ column_sql }} is not null
  and {{ column_sql }} not in ({{ values_sql }})
{% endtest %}


{% test dq_range(model, rule_id, column_sql, column_name_text, min_value=none, max_value=none) %}
select '{{ rule_id }}' as rule_id, _scenario_id, _row_id,
       '{{ column_name_text }}' as implicated_columns,
       cast({{ column_sql }} as varchar) as observed,
       'between {{ min_value if min_value is not none else "-inf" }} and {{ max_value if max_value is not none else "+inf" }}' as expected
from {{ model }}
where {{ column_sql }} is not null
  and (
      false
      {% if min_value is not none %} or {{ column_sql }} < {{ min_value }} {% endif %}
      {% if max_value is not none %} or {{ column_sql }} > {{ max_value }} {% endif %}
  )
{% endtest %}


{% test dq_expression(model, rule_id, condition, columns_text, observed_sql) %}
{#- A row violates the rule when the condition evaluates to false (NULL inputs are left to not_null). -#}
select '{{ rule_id }}' as rule_id, _scenario_id, _row_id,
       '{{ columns_text }}' as implicated_columns,
       {{ observed_sql }} as observed,
       'holds: {{ condition | replace("'", "") | replace('"', "") }}' as expected
from {{ model }}
where coalesce(({{ condition }}), true) = false
{% endtest %}


{% test dq_envelope(model, rule_id, expression, columns_text) %}
{#- Statistical envelope: bounds were fitted on the reference partition and loaded into dq_reference_bounds. -#}
with b as (
    select lower_bound, upper_bound
    from {{ source('dq_meta', 'dq_reference_bounds') }}
    where rule_id = '{{ rule_id }}'
),
v as (
    select _scenario_id, _row_id, ({{ expression }})::double as x from {{ model }}
)
select '{{ rule_id }}' as rule_id, v._scenario_id, v._row_id,
       '{{ columns_text }}' as implicated_columns,
       cast(round(v.x, 6) as varchar) as observed,
       'within reference envelope [' || cast(round(b.lower_bound, 6) as varchar) || ', '
           || cast(round(b.upper_bound, 6) as varchar) || ']' as expected
from v cross join b
where v.x is not null and (v.x < b.lower_bound or v.x > b.upper_bound)
{% endtest %}


{% test dq_rare_category(model, rule_id, expression, columns_text) %}
{#- Value (or value combination) absent or rare (< min_share) in the reference partition. -#}
with allowed as (
    select value from {{ source('dq_meta', 'dq_reference_categories') }} where rule_id = '{{ rule_id }}'
),
v as (
    select _scenario_id, _row_id, cast(({{ expression }}) as varchar) as x from {{ model }}
)
select '{{ rule_id }}' as rule_id, v._scenario_id, v._row_id,
       '{{ columns_text }}' as implicated_columns,
       v.x as observed,
       'value seen in reference with sufficient frequency' as expected
from v
where v.x is not null and v.x not in (select value from allowed)
{% endtest %}
