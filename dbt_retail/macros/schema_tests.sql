{#
    Custom tests cho ngành bán lẻ
#}

{% test positive_value(model, column_name) %}
    SELECT *
    FROM {{ model }}
    WHERE {{ column_name }} < 0
{% endtest %}

{% test profit_margin_range(model, column_name) %}
    SELECT *
    FROM {{ model }}
    WHERE {{ column_name }} < -1 OR {{ column_name }} > 1
{% endtest %}

{% test not_future_date(model, column_name) %}
    SELECT *
    FROM {{ model }}
    WHERE {{ column_name }} > CURRENT_DATE
{% endtest %}

{% test transaction_consistency(model, column_id, gross_column, discount_column, net_column) %}
    SELECT *
    FROM {{ model }}
    WHERE ABS({{ gross_column }} - {{ discount_column }} - {{ net_column }}) > 0.01
{% endtest %}
