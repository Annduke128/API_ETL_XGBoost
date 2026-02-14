"""
Redis Buffer cho data pipeline
Hỗ trợ: caching, queue, rate limiting
"""

import redis
import json
import pickle
import hashlib
from typing import Any, Optional, List, Dict
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class RedisBuffer:
    """Redis buffer cho data pipeline"""
    
    def __init__(self, host: str = 'localhost', port: int = 6379, 
                 db: int = 0, password: Optional[str] = None):
        self.client = redis.Redis(
            host=host,
            port=port,
            db=db,
            password=password,
            decode_responses=False  # Để hỗ trợ pickle
        )
        self.prefix = "retail_pipeline"
    
    def _make_key(self, key: str) -> str:
        """Tạo key với prefix"""
        return f"{self.prefix}:{key}"
    
    def cache_dataframe(self, key: str, df, expire: int = 3600):
        """Cache pandas DataFrame"""
        try:
            data = pickle.dumps(df)
            self.client.setex(
                self._make_key(f"df:{key}"),
                expire,
                data
            )
            logger.info(f"Cached DataFrame: {key}")
        except Exception as e:
            logger.error(f"Error caching DataFrame: {e}")
    
    def get_cached_dataframe(self, key: str) -> Optional[Any]:
        """Lấy cached DataFrame"""
        try:
            data = self.client.get(self._make_key(f"df:{key}"))
            if data:
                return pickle.loads(data)
            return None
        except Exception as e:
            logger.error(f"Error getting cached DataFrame: {e}")
            return None
    
    def push_to_queue(self, queue_name: str, data: Dict, priority: int = 0):
        """Push data vào priority queue"""
        key = self._make_key(f"queue:{queue_name}")
        item = {
            'data': data,
            'timestamp': datetime.now().isoformat(),
            'priority': priority
        }
        # Sử dụng sorted set cho priority queue
        self.client.zadd(key, {json.dumps(item): priority})
        logger.debug(f"Pushed to queue {queue_name}: {data.get('id', 'unknown')}")
    
    def pop_from_queue(self, queue_name: str) -> Optional[Dict]:
        """Pop data từ queue (highest priority first)"""
        key = self._make_key(f"queue:{queue_name}")
        # Lấy item có score thấp nhất (priority cao nhất)
        items = self.client.zrange(key, 0, 0)
        if items:
            item_data = json.loads(items[0])
            self.client.zrem(key, items[0])
            return item_data
        return None
    
    def get_queue_length(self, queue_name: str) -> int:
        """Lấy số lượng item trong queue"""
        key = self._make_key(f"queue:{queue_name}")
        return self.client.zcard(key)
    
    def cache_validation_result(self, file_hash: str, result: Dict, expire: int = 86400):
        """Cache kết quả validation"""
        key = self._make_key(f"validation:{file_hash}")
        self.client.setex(key, expire, json.dumps(result))
    
    def get_cached_validation(self, file_hash: str) -> Optional[Dict]:
        """Lấy cached validation result"""
        key = self._make_key(f"validation:{file_hash}")
        data = self.client.get(key)
        if data:
            return json.loads(data)
        return None
    
    def set_processing_status(self, job_id: str, status: str, metadata: Dict = None):
        """Set trạng thái xử lý"""
        key = self._make_key(f"status:{job_id}")
        data = {
            'status': status,
            'updated_at': datetime.now().isoformat(),
            'metadata': metadata or {}
        }
        self.client.setex(key, 3600, json.dumps(data))
    
    def get_processing_status(self, job_id: str) -> Optional[Dict]:
        """Lấy trạng thái xử lý"""
        key = self._make_key(f"status:{job_id}")
        data = self.client.get(key)
        if data:
            return json.loads(data)
        return None
    
    def acquire_lock(self, lock_name: str, timeout: int = 60) -> bool:
        """Acquire distributed lock"""
        key = self._make_key(f"lock:{lock_name}")
        return self.client.set(key, "1", nx=True, ex=timeout)
    
    def release_lock(self, lock_name: str):
        """Release distributed lock"""
        key = self._make_key(f"lock:{lock_name}")
        self.client.delete(key)
    
    def increment_counter(self, counter_name: str, amount: int = 1) -> int:
        """Tăng counter"""
        key = self._make_key(f"counter:{counter_name}")
        return self.client.incrby(key, amount)
    
    def get_counter(self, counter_name: str) -> int:
        """Lấy giá trị counter"""
        key = self._make_key(f"counter:{counter_name}")
        value = self.client.get(key)
        return int(value) if value else 0
    
    def add_to_batch(self, batch_key: str, data: Dict, max_size: int = 1000) -> List[Dict]:
        """Thêm vào batch, trả về batch đầy nếu có"""
        key = self._make_key(f"batch:{batch_key}")
        self.client.lpush(key, json.dumps(data))
        
        # Kiểm tra kích thước batch
        size = self.client.llen(key)
        if size >= max_size:
            # Lấy toàn bộ batch
            items = self.client.lrange(key, 0, max_size - 1)
            self.client.ltrim(key, max_size, -1)
            return [json.loads(item) for item in items]
        
        return []
    
    def flush_batch(self, batch_key: str) -> List[Dict]:
        """Lấy toàn bộ batch còn lại"""
        key = self._make_key(f"batch:{batch_key}")
        items = self.client.lrange(key, 0, -1)
        self.client.delete(key)
        return [json.loads(item) for item in items]
    
    def cache_dedup_key(self, key_value: str, expire: int = 86400):
        """Cache key để deduplication"""
        key = self._make_key(f"dedup:{hashlib.md5(key_value.encode()).hexdigest()}")
        self.client.setex(key, expire, "1")
    
    def is_duplicate(self, key_value: str) -> bool:
        """Kiểm tra xem key đã tồn tại chưa"""
        key = self._make_key(f"dedup:{hashlib.md5(key_value.encode()).hexdigest()}")
        return self.client.exists(key) > 0
    
    def clear_all(self, pattern: str = "*"):
        """Xóa tất cả key theo pattern"""
        full_pattern = self._make_key(pattern)
        keys = self.client.keys(full_pattern)
        if keys:
            self.client.delete(*keys)
            logger.info(f"Cleared {len(keys)} keys")
    
    def health_check(self) -> bool:
        """Kiểm tra kết nối Redis"""
        try:
            return self.client.ping()
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return False


# Singleton instance
_buffer = None

def get_buffer(host: str = 'localhost', port: int = 6379) -> RedisBuffer:
    """Lấy RedisBuffer instance (singleton)"""
    global _buffer
    if _buffer is None:
        _buffer = RedisBuffer(host=host, port=port)
    return _buffer
