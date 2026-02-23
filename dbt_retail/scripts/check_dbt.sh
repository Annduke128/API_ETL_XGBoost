#!/bin/bash
# Script kiểm tra DBT project trước khi chạy

echo "=========================================="
echo "DBT PROJECT HEALTH CHECK"
echo "=========================================="

# Check profiles.yml exists
if [ ! -f "profiles.yml" ]; then
    echo "❌ profiles.yml not found!"
    exit 1
fi
echo "✅ profiles.yml exists"

# Check dbt_project.yml exists
if [ ! -f "dbt_project.yml" ]; then
    echo "❌ dbt_project.yml not found!"
    exit 1
fi
echo "✅ dbt_project.yml exists"

# Check packages.yml exists
if [ ! -f "packages.yml" ]; then
    echo "⚠️  packages.yml not found (optional)"
else
    echo "✅ packages.yml exists"
fi

# Check models directory
if [ ! -d "models" ]; then
    echo "❌ models directory not found!"
    exit 1
fi
echo "✅ models directory exists"

# Count models
MODEL_COUNT=$(find models -name "*.sql" | wc -l)
echo "📊 Found $MODEL_COUNT models"

# Check for syntax errors
echo ""
echo "🔍 Running dbt compile (syntax check)..."
dbt compile --quiet

if [ $? -eq 0 ]; then
    echo "✅ No syntax errors found!"
else
    echo "❌ Syntax errors detected!"
    exit 1
fi

echo ""
echo "=========================================="
echo "All checks passed!"
echo "=========================================="
