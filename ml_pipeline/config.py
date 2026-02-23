"""
Configuration management cho ML Pipeline trên K3s
"""

import os
from typing import Dict, Any


class Config:
    """Base configuration class"""
    
    # Database - PostgreSQL
    POSTGRES_HOST = os.getenv('POSTGRES_HOST', 'postgres')
    POSTGRES_PORT = int(os.getenv('POSTGRES_PORT', '5432'))
    POSTGRES_DB = os.getenv('POSTGRES_DB', 'retail_db')
    POSTGRES_USER = os.getenv('POSTGRES_USER', 'retail_user')
    POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD', 'retail_password')
    
    # Database - ClickHouse
    CLICKHOUSE_HOST = os.getenv('CLICKHOUSE_HOST', 'clickhouse')
    CLICKHOUSE_PORT = os.getenv('CLICKHOUSE_PORT', '8123')
    CLICKHOUSE_DB = os.getenv('CLICKHOUSE_DB', 'retail_dw')
    CLICKHOUSE_USER = os.getenv('CLICKHOUSE_USER', 'default')
    CLICKHOUSE_PASSWORD = os.getenv('CLICKHOUSE_PASSWORD', '')
    
    # Redis
    REDIS_HOST = os.getenv('REDIS_HOST', 'redis')
    REDIS_PORT = int(os.getenv('REDIS_PORT', '6379'))
    REDIS_PASSWORD = os.getenv('REDIS_PASSWORD', '')
    
    # Application
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    MODEL_DIR = os.getenv('MODEL_DIR', '/app/models')
    PYTHONUNBUFFERED = os.getenv('PYTHONUNBUFFERED', '1')
    
    # K8s specific
    POD_NAME = os.getenv('HOSTNAME', '')
    NAMESPACE = os.getenv('NAMESPACE', 'default')
    
    # ML Settings
    DEFAULT_TRIALS = int(os.getenv('ML_TRIALS', '30'))
    CV_SPLITS = int(os.getenv('ML_CV_SPLITS', '3'))
    RANDOM_STATE = int(os.getenv('ML_RANDOM_STATE', '42'))
    
    @classmethod
    def is_kubernetes(cls) -> bool:
        """Check if running in Kubernetes"""
        return os.path.exists('/var/run/secrets/kubernetes.io/serviceaccount/token')
    
    @classmethod
    def get_resource_limits(cls) -> Dict[str, Any]:
        """Get CPU/Memory limits từ cgroup (K8s)"""
        limits = {'cpu': 1, 'memory_gb': 4, 'detected': False}
        
        try:
            # Read CPU limit từ cgroup v2
            cpu_max_path = '/sys/fs/cgroup/cpu.max'
            cpu_quota_path = '/sys/fs/cgroup/cpu/cpu.cfs_quota_us'
            cpu_period_path = '/sys/fs/cgroup/cpu/cpu.cfs_period_us'
            
            if os.path.exists(cpu_max_path):
                with open(cpu_max_path) as f:
                    content = f.read().strip()
                    if content != "max":
                        quota, period = content.split()
                        limits['cpu'] = int(quota) // int(period)
                        limits['detected'] = True
            elif os.path.exists(cpu_quota_path):
                with open(cpu_quota_path) as f:
                    quota = int(f.read().strip())
                with open(cpu_period_path) as f:
                    period = int(f.read().strip())
                if quota > 0:
                    limits['cpu'] = quota // period
                    limits['detected'] = True
        except Exception:
            pass
        
        try:
            # Read memory limit từ cgroup v2 hoặc v1
            mem_path_v2 = '/sys/fs/cgroup/memory.max'
            mem_path_v1 = '/sys/fs/cgroup/memory/memory.limit_in_bytes'
            
            mem_file = mem_path_v2 if os.path.exists(mem_path_v2) else mem_path_v1
            with open(mem_file) as f:
                mem_bytes = int(f.read().strip())
                if mem_bytes < (1024**4):  # Không phải max value
                    limits['memory_gb'] = mem_bytes // (1024**3)
                    limits['detected'] = True
        except Exception:
            pass
            
        return limits
    
    @classmethod
    def get_parallel_jobs(cls) -> int:
        """Tính toán số parallel jobs dựa trên CPU limits"""
        limits = cls.get_resource_limits()
        cpu = limits['cpu']
        # Để lại 1 core cho system, tối thiểu 1 job
        return max(1, cpu - 1) if cpu > 1 else 1
    
    @classmethod
    def to_dict(cls) -> Dict[str, Any]:
        """Export config as dictionary"""
        return {
            'postgres_host': cls.POSTGRES_HOST,
            'clickhouse_host': cls.CLICKHOUSE_HOST,
            'redis_host': cls.REDIS_HOST,
            'model_dir': cls.MODEL_DIR,
            'is_kubernetes': cls.is_kubernetes(),
            'resource_limits': cls.get_resource_limits(),
            'pod_name': cls.POD_NAME,
            'namespace': cls.NAMESPACE,
        }


class DevelopmentConfig(Config):
    """Development configuration"""
    LOG_LEVEL = 'DEBUG'
    DEFAULT_TRIALS = 10


class ProductionConfig(Config):
    """Production configuration"""
    LOG_LEVEL = 'INFO'
    DEFAULT_TRIALS = 50


# Config mapping
config_map = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': Config
}


def get_config(env: str = None):
    """Get configuration based on environment"""
    if env is None:
        env = os.getenv('ENVIRONMENT', 'default')
    return config_map.get(env, Config)
