{#
    Macros tiện ích cho ngành bán lẻ
#}

{% macro calculate_growth(current_value, previous_value) %}
    CASE 
        WHEN {{ previous_value }} = 0 OR {{ previous_value }} IS NULL THEN NULL
        ELSE ({{ current_value }} - {{ previous_value }}) / {{ previous_value }}
    END
{% endmacro %}

{% macro calculate_margin(profit, revenue) %}
    CASE 
        WHEN {{ revenue }} = 0 OR {{ revenue }} IS NULL THEN 0
        ELSE {{ profit }} / {{ revenue }}
    END
{% endmacro %}

{% macro format_currency(amount, currency='VND') %}
    CASE 
        WHEN '{{ currency }}' = 'VND' THEN CONCAT(FORMAT('%,.0f', {{ amount }}), ' ₫')
        ELSE CONCAT('{{ currency }} ', FORMAT('%,.2f', {{ amount }}))
    END
{% endmacro %}

{% macro days_since(date_column) %}
    CURRENT_DATE - {{ date_column }}
{% endmacro %}

{% macro is_weekend(date_column) %}
    EXTRACT(DOW FROM {{ date_column }}) IN (0, 6)
{% endmacro %}

{% macro time_of_day(hour_column) %}
    CASE 
        WHEN {{ hour_column }} >= 5 AND {{ hour_column }} < 12 THEN 'Morning'
        WHEN {{ hour_column }} >= 12 AND {{ hour_column }} < 18 THEN 'Afternoon'
        WHEN {{ hour_column }} >= 18 AND {{ hour_column }} < 22 THEN 'Evening'
        ELSE 'Night'
    END
{% endmacro %}

{% macro categorize_sales_velocity(velocity_column, fast=10, medium=3) %}
    CASE 
        WHEN {{ velocity_column }} >= {{ fast }} THEN 'Fast'
        WHEN {{ velocity_column }} >= {{ medium }} THEN 'Medium'
        WHEN {{ velocity_column }} > 0 THEN 'Slow'
        ELSE 'Dead'
    END
{% endmacro %}

{% macro calculate_abc_class(revenue_column, total_revenue_column, a_threshold=0.8, b_threshold=0.95) %}
    CASE 
        WHEN SUM({{ revenue_column }}) OVER (ORDER BY {{ revenue_column }} DESC) 
             / {{ total_revenue_column }} <= {{ a_threshold }} THEN 'A'
        WHEN SUM({{ revenue_column }}) OVER (ORDER BY {{ revenue_column }} DESC) 
             / {{ total_revenue_column }} <= {{ b_threshold }} THEN 'B'
        ELSE 'C'
    END
{% endmacro %}
