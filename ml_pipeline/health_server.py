"""
Health check server cho Kubernetes probes
Cung cấp /health, /ready, /metrics endpoints
"""

import logging
import threading
import time
from flask import Flask, jsonify, Response
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST, Counter, Histogram, Gauge

app = Flask(__name__)
logger = logging.getLogger(__name__)

# Global health state
_health_state = {
    'ready': False,
    'live': True,
    'startup_time': time.time(),
    'last_training': None,
    'model_loaded': False,
    'training_in_progress': False,
}

# Prometheus metrics
TRAINING_DURATION = Histogram(
    'ml_training_duration_seconds',
    'Time spent training models',
    ['model_name']
)

TRAINING_ERRORS = Counter(
    'ml_training_errors_total',
    'Total training errors',
    ['model_name', 'error_type']
)

PREDICTION_DURATION = Histogram(
    'ml_prediction_duration_seconds',
    'Time spent making predictions',
    ['model_name']
)

MODEL_SCORE = Gauge(
    'ml_model_score',
    'Model performance score',
    ['model_name', 'metric']
)

ACTIVE_MODELS = Gauge(
    'ml_active_models',
    'Number of active loaded models'
)


@app.route('/health')
def health():
    """Liveness probe - kiểm tra process còn sống"""
    if _health_state['live']:
        return jsonify({
            'status': 'healthy',
            'uptime_seconds': int(time.time() - _health_state['startup_time'])
        }), 200
    return jsonify({'status': 'unhealthy'}), 503


@app.route('/ready')
def ready():
    """Readiness probe - kiểm tra sẵn sàng nhận traffic"""
    if _health_state['ready']:
        return jsonify({
            'status': 'ready',
            'model_loaded': _health_state['model_loaded'],
            'last_training': _health_state['last_training']
        }), 200
    return jsonify({
        'status': 'not ready',
        'reason': 'initialization in progress'
    }), 503


@app.route('/startup')
def startup():
    """Startup probe - kiểm tra khởi động thành công"""
    # Startup probe đảm bảo container không bị kill quá sớm
    uptime = time.time() - _health_state['startup_time']
    if uptime > 5:  # Đợi ít nhất 5 giây
        return jsonify({'status': 'started', 'uptime': uptime}), 200
    return jsonify({'status': 'starting', 'uptime': uptime}), 503


@app.route('/metrics')
def metrics():
    """Prometheus metrics endpoint"""
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)


@app.route('/status')
def status():
    """Chi tiết trạng thái"""
    return jsonify({
        'health': _health_state,
        'uptime_seconds': int(time.time() - _health_state['startup_time'])
    })


def set_ready(ready: bool):
    """Set readiness status"""
    _health_state['ready'] = ready
    logger.info(f"Readiness set to: {ready}")


def set_live(live: bool):
    """Set liveness status"""
    _health_state['live'] = live
    logger.info(f"Liveness set to: {live}")


def set_model_loaded(loaded: bool):
    """Set model loaded status"""
    _health_state['model_loaded'] = loaded
    if loaded:
        ACTIVE_MODELS.set(1)
    else:
        ACTIVE_MODELS.set(0)


def set_training_in_progress(in_progress: bool):
    """Set training status"""
    _health_state['training_in_progress'] = in_progress
    if not in_progress:
        _health_state['last_training'] = time.strftime('%Y-%m-%dT%H:%M:%SZ')


def record_training_duration(model_name: str, duration: float):
    """Record training duration metric"""
    TRAINING_DURATION.labels(model_name=model_name).observe(duration)


def record_training_error(model_name: str, error_type: str):
    """Record training error"""
    TRAINING_ERRORS.labels(model_name=model_name, error_type=error_type).inc()


def record_prediction_duration(model_name: str, duration: float):
    """Record prediction duration"""
    PREDICTION_DURATION.labels(model_name=model_name).observe(duration)


def record_model_score(model_name: str, metric: str, score: float):
    """Record model score"""
    MODEL_SCORE.labels(model_name=model_name, metric=metric).set(score)


def start_health_server(port: int = 8080, host: str = '0.0.0.0'):
    """Start health server trong background thread"""
    def run():
        # Tắt Flask logging
        import flask
        flask.cli.show_server_banner = lambda *args: None
        log = logging.getLogger('werkzeug')
        log.setLevel(logging.ERROR)
        
        app.run(host=host, port=port, threaded=True, debug=False)
    
    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    logger.info(f"Health server started on {host}:{port}")
    
    # Đánh dấu live
    set_live(True)


if __name__ == '__main__':
    # Test mode
    start_health_server()
    
    # Giữ thread alive
    while True:
        time.sleep(1)
