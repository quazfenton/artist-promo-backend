"""
Comprehensive monitoring and health check system
"""
import asyncio
import time
import psutil
import redis
import logging
from typing import Dict, Any, List
from datetime import datetime, timedelta
from sqlalchemy import text
from app.database.connection import get_db
from app.models.database import Contact, Playlist, Venue
import os

logger = logging.getLogger(__name__)

class SystemMonitor:
    """Monitor system resources and performance"""
    
    def __init__(self):
        self.redis_client = self._get_redis_client()
        self.db = next(get_db())
        
    def _get_redis_client(self):
        """Initialize Redis client"""
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        try:
            return redis.from_url(redis_url)
        except Exception as e:
            logger.error(f"Could not connect to Redis: {e}")
            return None
    
    def get_system_metrics(self) -> Dict[str, Any]:
        """Get system resource metrics"""
        return {
            "cpu_percent": psutil.cpu_percent(interval=1),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_percent": psutil.disk_usage('/').percent,
            "process_memory_mb": psutil.Process().memory_info().rss / 1024 / 1024,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def get_redis_metrics(self) -> Dict[str, Any]:
        """Get Redis metrics"""
        if not self.redis_client:
            return {"error": "Redis not connected"}
        
        try:
            info = self.redis_client.info()
            return {
                "connected_clients": info.get("connected_clients", 0),
                "used_memory_mb": info.get("used_memory", 0) / 1024 / 1024,
                "total_commands_processed": info.get("total_commands_processed", 0),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
                "hit_rate": info.get("keyspace_hits", 0) / max(info.get("keyspace_hits", 0) + info.get("keyspace_misses", 1), 1),
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting Redis metrics: {e}")
            return {"error": str(e)}
    
    def get_database_metrics(self) -> Dict[str, Any]:
        """Get database metrics"""
        try:
            # Get basic stats
            contact_count = self.db.query(Contact).count()
            playlist_count = self.db.query(Playlist).count()
            venue_count = self.db.query(Venue).count()
            
            # Get recent activity
            recent_contacts = self.db.query(Contact).filter(
                Contact.created_at > datetime.utcnow() - timedelta(hours=24)
            ).count()
            
            # Get database connection info
            result = self.db.execute(text("SELECT 1")).fetchone()
            
            return {
                "contact_count": contact_count,
                "playlist_count": playlist_count,
                "venue_count": venue_count,
                "recent_contacts_24h": recent_contacts,
                "connection_status": "healthy" if result else "unreachable",
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting database metrics: {e}")
            return {"error": str(e)}
    
    def get_pipeline_metrics(self) -> Dict[str, Any]:
        """Get pipeline-specific metrics"""
        try:
            # Get metrics from Redis queues
            if self.redis_client:
                queue_metrics = {}
                for queue_name in ["scrape", "normalize", "resolve", "cluster", "outreach"]:
                    queue_key = f"queue:{queue_name}"
                    queue_length = self.redis_client.llen(queue_key)
                    queue_metrics[queue_name] = {
                        "length": queue_length,
                        "processing": self.redis_client.get(f"processing:{queue_name}") or 0
                    }
                
                # Get job metrics
                completed_jobs = self.redis_client.get("jobs:completed") or 0
                failed_jobs = self.redis_client.get("jobs:failed") or 0
                active_jobs = self.redis_client.get("jobs:active") or 0
                
                return {
                    "queues": queue_metrics,
                    "jobs_completed": int(completed_jobs),
                    "jobs_failed": int(failed_jobs),
                    "jobs_active": int(active_jobs),
                    "timestamp": datetime.utcnow().isoformat()
                }
            else:
                return {"error": "Redis not connected"}
        except Exception as e:
            logger.error(f"Error getting pipeline metrics: {e}")
            return {"error": str(e)}

class HealthChecker:
    """Comprehensive health checker"""
    
    def __init__(self):
        self.system_monitor = SystemMonitor()
    
    def check_system_health(self) -> Dict[str, Any]:
        """Check overall system health"""
        system_metrics = self.system_monitor.get_system_metrics()
        
        # Evaluate health based on thresholds
        cpu_high = system_metrics["cpu_percent"] > 80
        memory_high = system_metrics["memory_percent"] > 85
        disk_high = system_metrics["disk_percent"] > 90
        
        status = "healthy"
        if cpu_high or memory_high or disk_high:
            status = "degraded"
        
        return {
            "status": status,
            "metrics": system_metrics,
            "issues": {
                "high_cpu": cpu_high,
                "high_memory": memory_high,
                "high_disk": disk_high
            }
        }
    
    def check_database_health(self) -> Dict[str, Any]:
        """Check database health"""
        db_metrics = self.system_monitor.get_database_metrics()
        
        if "error" in db_metrics:
            return {
                "status": "unhealthy",
                "metrics": db_metrics,
                "error": db_metrics["error"]
            }
        
        # Check if database is responsive
        is_responsive = db_metrics["connection_status"] == "healthy"
        
        status = "healthy" if is_responsive else "unhealthy"
        
        return {
            "status": status,
            "metrics": db_metrics,
            "responsive": is_responsive
        }
    
    def check_redis_health(self) -> Dict[str, Any]:
        """Check Redis health"""
        redis_metrics = self.system_monitor.get_redis_metrics()
        
        if "error" in redis_metrics:
            return {
                "status": "unhealthy",
                "metrics": redis_metrics,
                "error": redis_metrics["error"]
            }
        
        # Check if Redis is responsive
        is_responsive = "connected_clients" in redis_metrics
        
        status = "healthy" if is_responsive else "unhealthy"
        
        return {
            "status": status,
            "metrics": redis_metrics,
            "responsive": is_responsive
        }
    
    def check_pipeline_health(self) -> Dict[str, Any]:
        """Check pipeline health"""
        pipeline_metrics = self.system_monitor.get_pipeline_metrics()
        
        if "error" in pipeline_metrics:
            return {
                "status": "unhealthy",
                "metrics": pipeline_metrics,
                "error": pipeline_metrics["error"]
            }
        
        # Check queue lengths for potential bottlenecks
        queues = pipeline_metrics.get("queues", {})
        queue_issues = {}
        
        for queue_name, queue_info in queues.items():
            # Flag queues with more than 100 items as potentially backed up
            if queue_info["length"] > 100:
                queue_issues[queue_name] = f"Queue has {queue_info['length']} items"
        
        status = "healthy" if not queue_issues else "degraded"
        
        return {
            "status": status,
            "metrics": pipeline_metrics,
            "queue_issues": queue_issues
        }
    
    def get_comprehensive_health(self) -> Dict[str, Any]:
        """Get comprehensive health check"""
        start_time = time.time()
        
        system_health = self.check_system_health()
        db_health = self.check_database_health()
        redis_health = self.check_redis_health()
        pipeline_health = self.check_pipeline_health()
        
        overall_status = "healthy"
        if any(h["status"] == "unhealthy" for h in [system_health, db_health, redis_health, pipeline_health]):
            overall_status = "unhealthy"
        elif any(h["status"] == "degraded" for h in [system_health, db_health, redis_health, pipeline_health]):
            overall_status = "degraded"
        
        response_time = (time.time() - start_time) * 1000  # ms
        
        return {
            "status": overall_status,
            "timestamp": datetime.utcnow().isoformat(),
            "response_time_ms": round(response_time, 2),
            "components": {
                "system": system_health,
                "database": db_health,
                "redis": redis_health,
                "pipeline": pipeline_health
            },
            "summary": {
                "system_status": system_health["status"],
                "database_status": db_health["status"],
                "redis_status": redis_health["status"],
                "pipeline_status": pipeline_health["status"]
            }
        }

class MetricsCollector:
    """Collect and store application metrics"""
    
    def __init__(self):
        self.redis_client = self.system_monitor.redis_client
    
    def increment_counter(self, name: str, value: int = 1):
        """Increment a counter metric"""
        if self.redis_client:
            try:
                self.redis_client.incr(name, value)
                self.redis_client.expire(name, 86400)  # Expire after 24 hours
            except Exception as e:
                logger.error(f"Error incrementing counter {name}: {e}")
    
    def set_gauge(self, name: str, value: float):
        """Set a gauge metric"""
        if self.redis_client:
            try:
                self.redis_client.set(name, value)
                self.redis_client.expire(name, 3600)  # Expire after 1 hour
            except Exception as e:
                logger.error(f"Error setting gauge {name}: {e}")
    
    def record_histogram(self, name: str, value: float):
        """Record a histogram value"""
        if self.redis_client:
            try:
                # Store as a time-series like structure
                key = f"{name}:{int(time.time())}"
                self.redis_client.set(key, value)
                self.redis_client.expire(key, 3600)  # Expire after 1 hour
            except Exception as e:
                logger.error(f"Error recording histogram {name}: {e}")
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get summary of collected metrics"""
        if not self.redis_client:
            return {"error": "Redis not connected"}
        
        try:
            # Get counters
            counters = {}
            for key in self.redis_client.scan_iter(match="counter:*"):
                value = self.redis_client.get(key)
                counters[key.decode()] = int(value) if value else 0
            
            # Get gauges
            gauges = {}
            for key in self.redis_client.scan_iter(match="gauge:*"):
                value = self.redis_client.get(key)
                gauges[key.decode()] = float(value) if value else 0.0
            
            return {
                "counters": counters,
                "gauges": gauges,
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting metrics summary: {e}")
            return {"error": str(e)}

# Global instances
health_checker = HealthChecker()
metrics_collector = MetricsCollector()

def get_health_status() -> Dict[str, Any]:
    """Get the current health status"""
    return health_checker.get_comprehensive_health()

def get_system_metrics() -> Dict[str, Any]:
    """Get system metrics"""
    return health_checker.system_monitor.get_system_metrics()

def get_database_metrics() -> Dict[str, Any]:
    """Get database metrics"""
    return health_checker.system_monitor.get_database_metrics()

def get_redis_metrics() -> Dict[str, Any]:
    """Get Redis metrics"""
    return health_checker.system_monitor.get_redis_metrics()

def get_pipeline_metrics() -> Dict[str, Any]:
    """Get pipeline metrics"""
    return health_checker.system_monitor.get_pipeline_metrics()

def get_metrics_summary() -> Dict[str, Any]:
    """Get metrics summary"""
    return metrics_collector.get_metrics_summary()

# Convenience functions for metrics
def increment_scrape_counter():
    """Increment scrape counter"""
    metrics_collector.increment_counter("counter:scrapes_total")

def increment_error_counter():
    """Increment error counter"""
    metrics_collector.increment_counter("counter:errors_total")

def record_response_time(response_time_ms: float):
    """Record API response time"""
    metrics_collector.record_histogram("histogram:response_time_ms", response_time_ms)

def set_active_users_count(count: int):
    """Set active users count"""
    metrics_collector.set_gauge("gauge:active_users", count)

def set_queue_length(queue_name: str, length: int):
    """Set queue length"""
    metrics_collector.set_gauge(f"gauge:queue_length:{queue_name}", length)