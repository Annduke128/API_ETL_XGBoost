#!/bin/bash
# Script giám sát pipeline K3s
# Usage: ./monitor-pipeline.sh [watch|logs|status]

NAMESPACE="hasu-ml"
MODE="${1:-status}"

case $MODE in
  status)
    echo "📋 Pipeline Status:"
    echo "=================="
    kubectl get jobs -n $NAMESPACE -o custom-columns=\
      NAME:.metadata.name,STATUS:.status.conditions[0].type,\
      COMPLETIONS:.status.succeeded/\/.spec.completions
    echo ""
    echo "📦 Recent Pods:"
    kubectl get pods -n $NAMESPACE --sort-by=.status.startTime | tail -15
    ;;
    
  logs)
    echo "🔍 Logs from recent jobs:"
    echo "========================"
    for job in spark-etl sync-data dbt-build ml-train ml-predict; do
      if kubectl get job $job -n $NAMESPACE 2>/dev/null | grep -q "1/1"; then
        echo ""
        echo "✅ $job - Last 10 lines:"
        kubectl logs -n $NAMESPACE job/$job --tail=10 2>/dev/null
      elif kubectl get job $job -n $NAMESPACE 2>/dev/null | grep -q "0/1"; then
        echo ""
        echo "🔄 $job - RUNNING (tail -f):"
        kubectl logs -n $NAMESPACE job/$job -f --tail=20
      fi
    done
    ;;
    
  watch)
    echo "👀 Watching pods... (Ctrl+C to exit)"
    kubectl get pods -n $NAMESPACE -w
    ;;
    
  events)
    echo "📊 Recent Events:"
    kubectl get events -n $NAMESPACE --sort-by='.lastTimestamp' | tail -30
    ;;
    
  *)
    echo "Usage: $0 [status|logs|watch|events]"
    echo "  status  - Show job completion status"
    echo "  logs    - Show logs from all jobs"
    echo "  watch   - Watch pods in real-time"
    echo "  events  - Show Kubernetes events"
    ;;
esac
