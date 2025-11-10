"""Redis caching layer for performance optimization"""
import redis
import json
import pickle
from typing import Any, Optional, Union, Callable
from functools import wraps
import hashlib
import os
from datetime import timedelta
from app.monitoring.metrics import MetricsCollector
from app.monitoring.logging import log_debug, log_warning

class CacheManager:
    """Redis-based caching manager"""
    
    def __init__(self):
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.redis_client = redis.from_url(self.redis_url, decode_responses=False)
        self.default_ttl = 3600  # 1 hour
    
    def _generate_key(self, prefix: str, *args, **kwargs) -> str:
        """Generate cache key from function arguments"""
        key_data = f"{prefix}:{args}:{sorted(kwargs.items())}"
        return f"cache:{hashlib.md5(key_data.encode()).hexdigest()}"
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        try:
            value = self.redis_client.get(key)
            if value is not None:
                MetricsCollector.track_cache_operation("get", "hit")
                log_debug("Cache hit", cache_key=key)
                return pickle.loads(value)
            else:
                MetricsCollector.track_cache_operation("get", "miss")
                log_debug("Cache miss", cache_key=key)
                return None
        except Exception as e:
            MetricsCollector.track_cache_operation("get", "error")
            log_warning("Cache get error", cache_key=key, error=str(e))
            return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in cache"""
        try:
            ttl = ttl or self.default_ttl
            serialized_value = pickle.dumps(value)
            result = self.redis_client.setex(key, ttl, serialized_value)
            
            MetricsCollector.track_cache_operation("set", "success")
            log_debug("Cache set", cache_key=key, ttl=ttl)
            return result
        except Exception as e:
            MetricsCollector.track_cache_operation("set", "error")
            log_warning("Cache set error", cache_key=key, error=str(e))
            return False
    
    def delete(self, key: str) -> bool:
        """Delete value from cache"""
        try:
            result = self.redis_client.delete(key)
            MetricsCollector.track_cache_operation("delete", "success")
            log_debug("Cache delete", cache_key=key)
            return bool(result)
        except Exception as e:
            MetricsCollector.track_cache_operation("delete", "error")
            log_warning("Cache delete error", cache_key=key, error=str(e))
            return False
    
    def clear_pattern(self, pattern: str) -> int:
        """Clear all keys matching pattern"""
        try:
            keys = self.redis_client.keys(pattern)
            if keys:
                result = self.redis_client.delete(*keys)
                log_debug("Cache pattern clear", pattern=pattern, keys_deleted=result)
                return result
            return 0
        except Exception as e:
            log_warning("Cache pattern clear error", pattern=pattern, error=str(e))
            return 0
    
    def exists(self, key: str) -> bool:
        """Check if key exists in cache"""
        try:
            return bool(self.redis_client.exists(key))
        except Exception:
            return False
    
    def get_stats(self) -> dict:
        """Get cache statistics"""
        try:
            info = self.redis_client.info()
            return {
                "memory_usage_mb": round(info.get('used_memory', 0) / 1024 / 1024, 2),
                "connected_clients": info.get('connected_clients', 0),
                "total_commands_processed": info.get('total_commands_processed', 0),
                "keyspace_hits": info.get('keyspace_hits', 0),
                "keyspace_misses": info.get('keyspace_misses', 0),
                "hit_rate": self._calculate_hit_rate(info)
            }
        except Exception as e:
            log_warning("Cache stats error", error=str(e))
            return {}
    
    def _calculate_hit_rate(self, info: dict) -> float:
        """Calculate cache hit rate"""
        hits = info.get('keyspace_hits', 0)
        misses = info.get('keyspace_misses', 0)
        total = hits + misses
        return (hits / total * 100) if total > 0 else 0

# Global cache manager instance
cache_manager = CacheManager()

# Caching decorators
def cache_result(ttl: int = 3600, key_prefix: str = None):
    """Decorator to cache function results"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Generate cache key
            prefix = key_prefix or f"{func.__module__}.{func.__name__}"
            cache_key = cache_manager._generate_key(prefix, *args, **kwargs)
            
            # Try to get from cache
            cached_result = cache_manager.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Execute function and cache result
            result = await func(*args, **kwargs)
            cache_manager.set(cache_key, result, ttl)
            return result
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Generate cache key
            prefix = key_prefix or f"{func.__module__}.{func.__name__}"
            cache_key = cache_manager._generate_key(prefix, *args, **kwargs)
            
            # Try to get from cache
            cached_result = cache_manager.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            cache_manager.set(cache_key, result, ttl)
            return result
        
        import asyncio
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator

def cache_invalidate(pattern: str):
    """Decorator to invalidate cache patterns after function execution"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)
            cache_manager.clear_pattern(pattern)
            return result
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            cache_manager.clear_pattern(pattern)
            return result
        
        import asyncio
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator

# Specific cache functions for common use cases
class ContactCache:
    """Contact-specific caching functions"""
    
    @staticmethod
    @cache_result(ttl=1800, key_prefix="contacts.search")
    def get_search_results(query: str, filters: dict, limit: int, offset: int):
        """Cache search results"""
        pass  # Implementation would be in the actual search function
    
    @staticmethod
    @cache_result(ttl=3600, key_prefix="contacts.stats")
    def get_dashboard_stats():
        """Cache dashboard statistics"""
        pass
    
    @staticmethod
    def invalidate_contact_cache(contact_id: int = None):
        """Invalidate contact-related cache"""
        patterns = [
            "cache:contacts.search:*",
            "cache:contacts.stats:*",
            "cache:analytics.*"
        ]
        
        if contact_id:
            patterns.append(f"cache:contacts.detail:{contact_id}:*")
        
        for pattern in patterns:
            cache_manager.clear_pattern(pattern)

class ScraperCache:
    """Scraper-specific caching functions"""
    
    @staticmethod
    @cache_result(ttl=7200, key_prefix="scraper.results")
    def get_recent_scraper_results(scraper_type: str, hours: int = 24):
        """Cache recent scraper results"""
        pass
    
    @staticmethod
    def invalidate_scraper_cache(scraper_type: str = None):
        """Invalidate scraper cache"""
        if scraper_type:
            cache_manager.clear_pattern(f"cache:scraper.results:{scraper_type}:*")
        else:
            cache_manager.clear_pattern("cache:scraper.*")

# Cache warming functions
async def warm_cache():
    """Warm up cache with frequently accessed data"""
    try:
        # Warm dashboard stats
        log_debug("Starting cache warming")
        
        # This would call actual functions that populate cache
        # ContactCache.get_dashboard_stats()
        # ScraperCache.get_recent_scraper_results("spotify")
        
        log_debug("Cache warming completed")
    except Exception as e:
        log_warning("Cache warming failed", error=str(e))

# Cache health check
def check_cache_health() -> dict:
    """Check cache health and performance"""
    try:
        # Test basic operations
        test_key = "health_check_test"
        test_value = {"timestamp": "test"}
        
        # Test set
        set_success = cache_manager.set(test_key, test_value, 60)
        
        # Test get
        get_result = cache_manager.get(test_key)
        get_success = get_result == test_value
        
        # Test delete
        delete_success = cache_manager.delete(test_key)
        
        # Get stats
        stats = cache_manager.get_stats()
        
        return {
            "status": "healthy" if all([set_success, get_success, delete_success]) else "unhealthy",
            "operations": {
                "set": set_success,
                "get": get_success,
                "delete": delete_success
            },
            "stats": stats
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }
