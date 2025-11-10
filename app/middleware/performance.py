"""Performance monitoring middleware"""
import time
import psutil
import asyncio
from typing import Dict, Any
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from app.monitoring.metrics import MetricsCollector
from app.monitoring.logging import structured_logger, log_warning
import os

class PerformanceMiddleware(BaseHTTPMiddleware):
    """Monitor request performance and system resources"""
    
    def __init__(self, app, slow_request_threshold: float = 1.0):
        super().__init__(app)
        self.slow_request_threshold = slow_request_threshold  # seconds
        self.process = psutil.Process(os.getpid())
    
    async def dispatch(self, request: Request, call_next):
        # Record start time and system state
        start_time = time.time()
        start_memory = self.process.memory_info().rss / 1024 / 1024  # MB
        start_cpu = self.process.cpu_percent()
        
        # Process request
        response = await call_next(request)
        
        # Calculate metrics
        duration = time.time() - start_time
        end_memory = self.process.memory_info().rss / 1024 / 1024  # MB
        memory_delta = end_memory - start_memory
        
        # Log performance metrics
        self._log_performance_metrics(
            request, response, duration, memory_delta, start_cpu
        )
        
        # Add performance headers
        response.headers["X-Response-Time"] = f"{duration:.3f}s"
        response.headers["X-Memory-Usage"] = f"{end_memory:.1f}MB"
        
        return response
    
    def _log_performance_metrics(self, request: Request, response: Response, 
                                duration: float, memory_delta: float, cpu_percent: float):
        """Log detailed performance metrics"""
        
        method = request.method
        path = request.url.path
        status_code = response.status_code
        
        # Track in Prometheus
        MetricsCollector.track_http_request(method, path, status_code, duration)
        
        # Log slow requests
        if duration > self.slow_request_threshold:
            log_warning(
                "Slow request detected",
                method=method,
                path=path,
                duration_ms=duration * 1000,
                status_code=status_code,
                memory_delta_mb=memory_delta,
                cpu_percent=cpu_percent
            )
        
        # Log to structured logger
        structured_logger.log_api_request(
            method, path, status_code, duration * 1000
        )

class ResourceMonitor:
    """Monitor system resources"""
    
    def __init__(self):
        self.process = psutil.Process(os.getpid())
        self._last_cpu_times = self.process.cpu_times()
        self._last_check = time.time()
    
    def get_system_metrics(self) -> Dict[str, Any]:
        """Get current system resource metrics"""
        
        # Memory metrics
        memory_info = self.process.memory_info()
        memory_percent = self.process.memory_percent()
        
        # CPU metrics
        cpu_percent = self.process.cpu_percent()
        cpu_times = self.process.cpu_times()
        
        # System-wide metrics
        system_memory = psutil.virtual_memory()
        system_cpu = psutil.cpu_percent(interval=None)
        
        # Disk usage
        disk_usage = psutil.disk_usage('/')
        
        # Network I/O
        net_io = psutil.net_io_counters()
        
        return {
            "process": {
                "memory_mb": memory_info.rss / 1024 / 1024,
                "memory_percent": memory_percent,
                "cpu_percent": cpu_percent,
                "cpu_times": {
                    "user": cpu_times.user,
                    "system": cpu_times.system
                },
                "threads": self.process.num_threads(),
                "open_files": len(self.process.open_files()),
                "connections": len(self.process.connections())
            },
            "system": {
                "memory_total_gb": system_memory.total / 1024 / 1024 / 1024,
                "memory_available_gb": system_memory.available / 1024 / 1024 / 1024,
                "memory_percent": system_memory.percent,
                "cpu_percent": system_cpu,
                "cpu_count": psutil.cpu_count(),
                "load_average": os.getloadavg() if hasattr(os, 'getloadavg') else None
            },
            "disk": {
                "total_gb": disk_usage.total / 1024 / 1024 / 1024,
                "used_gb": disk_usage.used / 1024 / 1024 / 1024,
                "free_gb": disk_usage.free / 1024 / 1024 / 1024,
                "percent": (disk_usage.used / disk_usage.total) * 100
            },
            "network": {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_sent": net_io.packets_sent,
                "packets_recv": net_io.packets_recv
            }
        }
    
    def check_resource_limits(self) -> Dict[str, bool]:
        """Check if resource usage exceeds safe limits"""
        
        metrics = self.get_system_metrics()
        
        warnings = {}
        
        # Memory warnings
        if metrics["process"]["memory_percent"] > 80:
            warnings["high_memory_usage"] = True
        
        if metrics["system"]["memory_percent"] > 90:
            warnings["system_memory_critical"] = True
        
        # CPU warnings
        if metrics["process"]["cpu_percent"] > 80:
            warnings["high_cpu_usage"] = True
        
        if metrics["system"]["cpu_percent"] > 90:
            warnings["system_cpu_critical"] = True
        
        # Disk warnings
        if metrics["disk"]["percent"] > 85:
            warnings["disk_space_low"] = True
        
        # Connection warnings
        if metrics["process"]["connections"] > 1000:
            warnings["high_connection_count"] = True
        
        return warnings

# Global resource monitor
resource_monitor = ResourceMonitor()

# Background task to monitor resources
async def monitor_resources():
    """Background task to continuously monitor system resources"""
    
    while True:
        try:
            # Get current metrics
            metrics = resource_monitor.get_system_metrics()
            warnings = resource_monitor.check_resource_limits()
            
            # Update Prometheus metrics
            from app.monitoring.metrics import (
                database_connections_active, active_contacts_total
            )
            
            # Update gauges (these would be populated from actual data sources)
            # database_connections_active.set(metrics["process"]["connections"])
            
            # Log warnings
            if warnings:
                log_warning(
                    "Resource usage warnings detected",
                    warnings=warnings,
                    metrics=metrics
                )
            
            # Sleep for 30 seconds
            await asyncio.sleep(30)
            
        except Exception as e:
            log_warning("Resource monitoring error", error=str(e))
            await asyncio.sleep(60)  # Wait longer on error

# Performance profiler for specific operations
class PerformanceProfiler:
    """Profile specific operations for performance analysis"""
    
    def __init__(self, operation_name: str):
        self.operation_name = operation_name
        self.start_time = None
        self.start_memory = None
        self.checkpoints = []
    
    def __enter__(self):
        self.start_time = time.time()
        self.start_memory = resource_monitor.process.memory_info().rss / 1024 / 1024
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        end_memory = resource_monitor.process.memory_info().rss / 1024 / 1024
        memory_delta = end_memory - self.start_memory
        
        # Log performance profile
        structured_logger.log_info(
            f"Performance profile: {self.operation_name}",
            extra={
                "event_type": "performance_profile",
                "operation": self.operation_name,
                "duration_ms": duration * 1000,
                "memory_delta_mb": memory_delta,
                "checkpoints": self.checkpoints,
                "success": exc_type is None
            }
        )
    
    def checkpoint(self, name: str):
        """Add a checkpoint to track sub-operation performance"""
        current_time = time.time()
        duration_from_start = current_time - self.start_time
        
        self.checkpoints.append({
            "name": name,
            "duration_from_start_ms": duration_from_start * 1000,
            "timestamp": current_time
        })

# Decorator for profiling functions
def profile_performance(operation_name: str = None):
    """Decorator to profile function performance"""
    def decorator(func):
        nonlocal operation_name
        if operation_name is None:
            operation_name = f"{func.__module__}.{func.__name__}"
        
        async def async_wrapper(*args, **kwargs):
            with PerformanceProfiler(operation_name):
                return await func(*args, **kwargs)
        
        def sync_wrapper(*args, **kwargs):
            with PerformanceProfiler(operation_name):
                return func(*args, **kwargs)
        
        import asyncio
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator
