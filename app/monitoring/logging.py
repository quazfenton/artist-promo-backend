"""Structured logging with correlation IDs"""
import uuid
import json
from datetime import datetime
from typing import Dict, Any, Optional
from contextvars import ContextVar
from loguru import logger
import sys

# Context variables for request tracking
request_id_var: ContextVar[str] = ContextVar('request_id', default='')
user_id_var: ContextVar[str] = ContextVar('user_id', default='')

class StructuredLogger:
    """Enhanced logging with structured data and correlation IDs"""
    
    def __init__(self):
        self._configure_logger()
    
    def _configure_logger(self):
        """Configure loguru with structured format"""
        
        # Remove default handler
        logger.remove()
        
        # Add structured JSON handler for production
        logger.add(
            sys.stdout,
            format=self._json_formatter,
            level="INFO",
            serialize=False
        )
        
        # Add file handler with rotation
        logger.add(
            "logs/app_{time:YYYY-MM-DD}.log",
            format=self._json_formatter,
            level="DEBUG",
            rotation="1 day",
            retention="7 days",
            compression="gz"
        )
        
        # Add error file handler
        logger.add(
            "logs/errors_{time:YYYY-MM-DD}.log",
            format=self._json_formatter,
            level="ERROR",
            rotation="1 day",
            retention="30 days"
        )
    
    def _json_formatter(self, record):
        """Format log record as structured JSON"""
        
        # Base log structure
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record["level"].name,
            "message": record["message"],
            "module": record["name"],
            "function": record["function"],
            "line": record["line"]
        }
        
        # Add correlation IDs if available
        request_id = request_id_var.get('')
        user_id = user_id_var.get('')
        
        if request_id:
            log_entry["request_id"] = request_id
        if user_id:
            log_entry["user_id"] = user_id
        
        # Add extra fields from record
        if record["extra"]:
            log_entry.update(record["extra"])
        
        # Add exception info if present
        if record["exception"]:
            log_entry["exception"] = {
                "type": record["exception"].type.__name__,
                "value": str(record["exception"].value),
                "traceback": record["exception"].traceback.format()
            }
        
        return json.dumps(log_entry) + "\n"
    
    def set_request_context(self, request_id: str, user_id: str = None):
        """Set request context for correlation"""
        request_id_var.set(request_id)
        if user_id:
            user_id_var.set(user_id)
    
    def clear_request_context(self):
        """Clear request context"""
        request_id_var.set('')
        user_id_var.set('')
    
    def log_api_request(self, method: str, path: str, status_code: int, 
                       duration_ms: float, user_id: str = None):
        """Log API request with structured data"""
        logger.info(
            "API request completed",
            extra={
                "event_type": "api_request",
                "http_method": method,
                "http_path": path,
                "http_status_code": status_code,
                "duration_ms": duration_ms,
                "user_id": user_id
            }
        )
    
    def log_scraper_event(self, scraper_type: str, event: str, 
                         results_count: int = None, duration_ms: float = None,
                         error: str = None):
        """Log scraper events"""
        extra_data = {
            "event_type": "scraper_event",
            "scraper_type": scraper_type,
            "scraper_event": event
        }
        
        if results_count is not None:
            extra_data["results_count"] = results_count
        if duration_ms is not None:
            extra_data["duration_ms"] = duration_ms
        if error:
            extra_data["error"] = error
        
        if error:
            logger.error(f"Scraper {event} failed", extra=extra_data)
        else:
            logger.info(f"Scraper {event}", extra=extra_data)
    
    def log_database_event(self, operation: str, table: str, 
                          record_count: int = None, duration_ms: float = None):
        """Log database operations"""
        logger.info(
            f"Database {operation}",
            extra={
                "event_type": "database_event",
                "db_operation": operation,
                "db_table": table,
                "record_count": record_count,
                "duration_ms": duration_ms
            }
        )
    
    def log_cache_event(self, operation: str, key: str, hit: bool = None):
        """Log cache operations"""
        extra_data = {
            "event_type": "cache_event",
            "cache_operation": operation,
            "cache_key": key
        }
        
        if hit is not None:
            extra_data["cache_hit"] = hit
        
        logger.debug("Cache operation", extra=extra_data)
    
    def log_task_event(self, task_type: str, task_id: str, event: str,
                      duration_ms: float = None, error: str = None):
        """Log background task events"""
        extra_data = {
            "event_type": "task_event",
            "task_type": task_type,
            "task_id": task_id,
            "task_event": event
        }
        
        if duration_ms is not None:
            extra_data["duration_ms"] = duration_ms
        if error:
            extra_data["error"] = error
        
        if error:
            logger.error(f"Task {event} failed", extra=extra_data)
        else:
            logger.info(f"Task {event}", extra=extra_data)
    
    def log_security_event(self, event_type: str, user_id: str = None, 
                          ip_address: str = None, details: Dict = None):
        """Log security-related events"""
        extra_data = {
            "event_type": "security_event",
            "security_event_type": event_type,
            "user_id": user_id,
            "ip_address": ip_address
        }
        
        if details:
            extra_data.update(details)
        
        logger.warning("Security event", extra=extra_data)

# Global logger instance
structured_logger = StructuredLogger()

# Middleware for request correlation
class LoggingMiddleware:
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        # Generate request ID
        request_id = str(uuid.uuid4())[:8]
        
        # Set request context
        structured_logger.set_request_context(request_id)
        
        # Add request ID to scope for access in endpoints
        scope["request_id"] = request_id
        
        try:
            await self.app(scope, receive, send)
        finally:
            # Clear context after request
            structured_logger.clear_request_context()

# Convenience functions
def log_info(message: str, **kwargs):
    """Log info message with extra data"""
    logger.info(message, extra=kwargs)

def log_error(message: str, error: Exception = None, **kwargs):
    """Log error message with exception details"""
    if error:
        kwargs["error_type"] = type(error).__name__
        kwargs["error_message"] = str(error)
    
    logger.error(message, extra=kwargs)

def log_warning(message: str, **kwargs):
    """Log warning message with extra data"""
    logger.warning(message, extra=kwargs)

def log_debug(message: str, **kwargs):
    """Log debug message with extra data"""
    logger.debug(message, extra=kwargs)

# Context manager for operation logging
class LogOperation:
    def __init__(self, operation_name: str, **context):
        self.operation_name = operation_name
        self.context = context
        self.start_time = None
    
    def __enter__(self):
        self.start_time = datetime.utcnow()
        log_info(f"Starting {self.operation_name}", **self.context)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = (datetime.utcnow() - self.start_time).total_seconds() * 1000
        
        if exc_type:
            log_error(
                f"Failed {self.operation_name}",
                error=exc_val,
                duration_ms=duration,
                **self.context
            )
        else:
            log_info(
                f"Completed {self.operation_name}",
                duration_ms=duration,
                **self.context
            )
