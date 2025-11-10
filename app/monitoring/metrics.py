"""Prometheus metrics collection"""
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from fastapi import Request, Response
from fastapi.responses import Response as FastAPIResponse
import time
from typing import Dict, Any
from functools import wraps

# Define metrics
http_requests_total = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status_code']
)

http_request_duration_seconds = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint']
)

scraper_requests_total = Counter(
    'scraper_requests_total',
    'Total scraper requests',
    ['scraper_type', 'status']
)

scraper_duration_seconds = Histogram(
    'scraper_duration_seconds',
    'Scraper execution duration in seconds',
    ['scraper_type']
)

database_connections_active = Gauge(
    'database_connections_active',
    'Active database connections'
)

database_query_duration_seconds = Histogram(
    'database_query_duration_seconds',
    'Database query duration in seconds',
    ['query_type']
)

cache_operations_total = Counter(
    'cache_operations_total',
    'Total cache operations',
    ['operation', 'status']
)

active_contacts_total = Gauge(
    'active_contacts_total',
    'Total active contacts in database'
)

task_queue_size = Gauge(
    'task_queue_size',
    'Number of tasks in queue',
    ['queue_name']
)

task_processing_duration_seconds = Histogram(
    'task_processing_duration_seconds',
    'Task processing duration in seconds',
    ['task_type']
)

email_campaigns_sent_total = Counter(
    'email_campaigns_sent_total',
    'Total email campaigns sent',
    ['campaign_type']
)

api_rate_limit_hits_total = Counter(
    'api_rate_limit_hits_total',
    'Total API rate limit hits',
    ['endpoint']
)

class MetricsCollector:
    """Centralized metrics collection"""
    
    @staticmethod
    def track_http_request(method: str, endpoint: str, status_code: int, duration: float):
        """Track HTTP request metrics"""
        http_requests_total.labels(
            method=method,
            endpoint=endpoint,
            status_code=str(status_code)
        ).inc()
        
        http_request_duration_seconds.labels(
            method=method,
            endpoint=endpoint
        ).observe(duration)
    
    @staticmethod
    def track_scraper_request(scraper_type: str, status: str, duration: float = None):
        """Track scraper request metrics"""
        scraper_requests_total.labels(
            scraper_type=scraper_type,
            status=status
        ).inc()
        
        if duration is not None:
            scraper_duration_seconds.labels(
                scraper_type=scraper_type
            ).observe(duration)
    
    @staticmethod
    def track_database_query(query_type: str, duration: float):
        """Track database query metrics"""
        database_query_duration_seconds.labels(
            query_type=query_type
        ).observe(duration)
    
    @staticmethod
    def track_cache_operation(operation: str, status: str):
        """Track cache operation metrics"""
        cache_operations_total.labels(
            operation=operation,
            status=status
        ).inc()
    
    @staticmethod
    def update_contact_count(count: int):
        """Update active contacts gauge"""
        active_contacts_total.set(count)
    
    @staticmethod
    def update_queue_size(queue_name: str, size: int):
        """Update task queue size"""
        task_queue_size.labels(queue_name=queue_name).set(size)
    
    @staticmethod
    def track_task_processing(task_type: str, duration: float):
        """Track task processing duration"""
        task_processing_duration_seconds.labels(
            task_type=task_type
        ).observe(duration)
    
    @staticmethod
    def track_email_campaign(campaign_type: str):
        """Track email campaign sent"""
        email_campaigns_sent_total.labels(
            campaign_type=campaign_type
        ).inc()
    
    @staticmethod
    def track_rate_limit_hit(endpoint: str):
        """Track rate limit hits"""
        api_rate_limit_hits_total.labels(
            endpoint=endpoint
        ).inc()

# Decorators for automatic metrics collection
def track_time(metric_name: str, labels: Dict[str, str] = None):
    """Decorator to track execution time"""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time
                
                if metric_name == "scraper_duration":
                    scraper_type = labels.get("scraper_type", "unknown") if labels else "unknown"
                    MetricsCollector.track_scraper_request(scraper_type, "success", duration)
                elif metric_name == "database_query":
                    query_type = labels.get("query_type", "unknown") if labels else "unknown"
                    MetricsCollector.track_database_query(query_type, duration)
                
                return result
            except Exception as e:
                duration = time.time() - start_time
                
                if metric_name == "scraper_duration":
                    scraper_type = labels.get("scraper_type", "unknown") if labels else "unknown"
                    MetricsCollector.track_scraper_request(scraper_type, "error", duration)
                
                raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                
                if metric_name == "database_query":
                    query_type = labels.get("query_type", "unknown") if labels else "unknown"
                    MetricsCollector.track_database_query(query_type, duration)
                
                return result
            except Exception as e:
                duration = time.time() - start_time
                raise
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator

async def metrics_endpoint():
    """Prometheus metrics endpoint"""
    return FastAPIResponse(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )

# Middleware for automatic HTTP metrics collection
class MetricsMiddleware:
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        start_time = time.time()
        
        # Extract request info
        method = scope["method"]
        path = scope["path"]
        
        # Normalize endpoint path (remove IDs)
        endpoint = self._normalize_path(path)
        
        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status_code = message["status"]
                duration = time.time() - start_time
                
                # Track metrics
                MetricsCollector.track_http_request(method, endpoint, status_code, duration)
            
            await send(message)
        
        await self.app(scope, receive, send_wrapper)
    
    def _normalize_path(self, path: str) -> str:
        """Normalize path by replacing IDs with placeholders"""
        import re
        
        # Replace numeric IDs
        path = re.sub(r'/\d+', '/{id}', path)
        
        # Replace UUIDs
        path = re.sub(r'/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', '/{uuid}', path)
        
        return path

import asyncio
