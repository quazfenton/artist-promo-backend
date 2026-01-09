"""Comprehensive error handling and graceful shutdown system"""
import asyncio
import signal
import sys
import traceback
import logging
from typing import Dict, Any, Optional, Callable
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exception_handlers import http_exception_handler
from starlette.middleware.base import BaseHTTPMiddleware
from contextlib import asynccontextmanager
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Sentry for error tracking (optional)
if os.getenv("SENTRY_DSN"):
    sentry_sdk.init(
        dsn=os.getenv("SENTRY_DSN"),
        integrations=[
            FastApiIntegration(transaction_style="endpoint"),
            SqlalchemyIntegration(),
        ],
        traces_sample_rate=1.0,
        profiles_sample_rate=1.0,
    )

class GlobalExceptionHandler:
    """Global exception handler for the application"""
    
    def __init__(self):
        self.error_counts = {}  # Track error frequency
        self.shutdown_requested = False
    
    def handle_exception(self, request: Request, exc: Exception) -> JSONResponse:
        """Handle exceptions globally"""
        # Log the error
        error_id = self._log_error(request, exc)
        
        # Track error frequency
        error_type = type(exc).__name__
        self.error_counts[error_type] = self.error_counts.get(error_type, 0) + 1
        
        # Determine response based on exception type
        if isinstance(exc, HTTPException):
            return JSONResponse(
                status_code=exc.status_code,
                content={
                    "error": exc.detail,
                    "error_id": error_id,
                    "timestamp": self._get_timestamp()
                }
            )
        elif isinstance(exc, ValueError):
            return JSONResponse(
                status_code=400,
                content={
                    "error": "Invalid input",
                    "details": str(exc),
                    "error_id": error_id,
                    "timestamp": self._get_timestamp()
                }
            )
        elif isinstance(exc, PermissionError):
            return JSONResponse(
                status_code=403,
                content={
                    "error": "Permission denied",
                    "error_id": error_id,
                    "timestamp": self._get_timestamp()
                }
            )
        else:
            # Log unexpected errors
            logger.error(f"Unexpected error: {str(exc)}", exc_info=True)
            
            # In production, don't expose internal error details
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Internal server error",
                    "error_id": error_id,
                    "timestamp": self._get_timestamp()
                }
            )
    
    def _log_error(self, request: Request, exc: Exception) -> str:
        """Log error with context"""
        import uuid
        error_id = str(uuid.uuid4())
        
        error_context = {
            "error_id": error_id,
            "method": request.method,
            "url": str(request.url),
            "headers": dict(request.headers),
            "error_type": type(exc).__name__,
            "error_message": str(exc),
            "timestamp": self._get_timestamp(),
            "traceback": traceback.format_exc() if exc.__traceback__ else None
        }
        
        logger.error(f"Error {error_id}: {str(exc)}", extra=error_context)
        
        return error_id
    
    def _get_timestamp(self) -> str:
        """Get ISO format timestamp"""
        from datetime import datetime
        return datetime.utcnow().isoformat()

# Global exception handler instance
global_exception_handler = GlobalExceptionHandler()

class ErrorTrackingMiddleware(BaseHTTPMiddleware):
    """Middleware to track errors and add correlation IDs"""
    
    async def dispatch(self, request: Request, call_next):
        # Add correlation ID to request
        correlation_id = request.headers.get("X-Correlation-ID") or self._generate_correlation_id()
        request.state.correlation_id = correlation_id
        
        try:
            response = await call_next(request)
            
            # Log successful requests
            if response.status_code >= 400:
                logger.warning(
                    f"Request failed: {request.method} {request.url} - {response.status_code}",
                    extra={
                        "correlation_id": correlation_id,
                        "status_code": response.status_code
                    }
                )
            
            # Add correlation ID to response
            response.headers["X-Correlation-ID"] = correlation_id
            
            return response
        except Exception as exc:
            # Handle exceptions
            error_response = global_exception_handler.handle_exception(request, exc)
            error_response.headers["X-Correlation-ID"] = correlation_id
            return error_response
    
    def _generate_correlation_id(self) -> str:
        """Generate a correlation ID"""
        import uuid
        return str(uuid.uuid4())

# Graceful shutdown manager
class GracefulShutdownManager:
    """Manage graceful shutdown of the application"""
    
    def __init__(self):
        self.shutdown_requested = False
        self.active_tasks = set()
        self.cleanup_functions = []
    
    def add_cleanup_function(self, func: Callable):
        """Add a cleanup function to be called during shutdown"""
        self.cleanup_functions.append(func)
    
    def add_task(self, task: asyncio.Task):
        """Track an active task"""
        self.active_tasks.add(task)
        task.add_done_callback(self.active_tasks.discard)
    
    async def shutdown(self):
        """Perform graceful shutdown"""
        logger.info("Initiating graceful shutdown...")
        self.shutdown_requested = True
        
        # Cancel all active tasks
        for task in self.active_tasks.copy():
            if not task.done():
                logger.info(f"Cancelling task: {task.get_name() if hasattr(task, 'get_name') else 'unnamed'}")
                task.cancel()
        
        # Wait for tasks to complete cancellation
        if self.active_tasks:
            await asyncio.gather(*self.active_tasks, return_exceptions=True)
        
        # Run cleanup functions
        for cleanup_func in self.cleanup_functions:
            try:
                if asyncio.iscoroutinefunction(cleanup_func):
                    await cleanup_func()
                else:
                    cleanup_func()
            except Exception as e:
                logger.error(f"Error during cleanup: {e}")
        
        logger.info("Graceful shutdown completed")
    
    def request_shutdown(self):
        """Request application shutdown"""
        self.shutdown_requested = True

# Global shutdown manager
shutdown_manager = GracefulShutdownManager()

def setup_signal_handlers():
    """Setup signal handlers for graceful shutdown"""
    
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        # Don't use asyncio.run() here as the event loop is already running
        # Instead, schedule the shutdown coroutine
    
    # Handle SIGTERM and SIGINT
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

# Custom exception classes
class AppError(Exception):
    """Base application error"""
    def __init__(self, message: str, status_code: int = 500, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details or {}

class ValidationError(AppError):
    """Validation error"""
    def __init__(self, message: str, field: str = None, value: Any = None):
        details = {"field": field, "value": value} if field else {}
        super().__init__(message, 400, details)

class NotFoundError(AppError):
    """Not found error"""
    def __init__(self, resource: str, identifier: str = None):
        message = f"{resource} not found"
        if identifier:
            message += f": {identifier}"
        super().__init__(message, 404)

class UnauthorizedError(AppError):
    """Unauthorized error"""
    def __init__(self, message: str = "Unauthorized"):
        super().__init__(message, 401)

class ForbiddenError(AppError):
    """Forbidden error"""
    def __init__(self, message: str = "Forbidden"):
        super().__init__(message, 403)

# Exception handlers for FastAPI
async def validation_exception_handler(request: Request, exc: ValidationError):
    """Handle validation errors"""
    return global_exception_handler.handle_exception(request, exc)

async def not_found_exception_handler(request: Request, exc: NotFoundError):
    """Handle not found errors"""
    return global_exception_handler.handle_exception(request, exc)

async def unauthorized_exception_handler(request: Request, exc: UnauthorizedError):
    """Handle unauthorized errors"""
    return global_exception_handler.handle_exception(request, exc)

async def forbidden_exception_handler(request: Request, exc: ForbiddenError):
    """Handle forbidden errors"""
    return global_exception_handler.handle_exception(request, exc)

# Register exception handlers with FastAPI
def register_exception_handlers(app: FastAPI):
    """Register custom exception handlers with FastAPI app"""
    app.add_exception_handler(ValidationError, validation_exception_handler)
    app.add_exception_handler(NotFoundError, not_found_exception_handler)
    app.add_exception_handler(UnauthorizedError, unauthorized_exception_handler)
    app.add_exception_handler(ForbiddenError, forbidden_exception_handler)
    
    # Register global exception handler for unhandled exceptions
    @app.exception_handler(Exception)
    async def global_exception_handler_wrapper(request: Request, exc: Exception):
        return global_exception_handler.handle_exception(request, exc)

# Utility functions for error handling
def handle_db_error(exc: Exception, operation: str = "database operation"):
    """Handle database errors appropriately"""
    error_msg = f"Database error during {operation}: {str(exc)}"
    logger.error(error_msg, exc_info=True)
    
    # Depending on the specific database error, you might want to return different responses
    if "connection" in str(exc).lower() or "timeout" in str(exc).lower():
        raise AppError("Database temporarily unavailable", 503)
    else:
        raise AppError("Database operation failed", 500)

def handle_external_api_error(exc: Exception, service: str = "external service"):
    """Handle errors from external API calls"""
    error_msg = f"Error calling {service}: {str(exc)}"
    logger.error(error_msg, exc_info=True)
    
    # If it's a timeout or connection error, it might be temporary
    if "timeout" in str(exc).lower() or "connection" in str(exc).lower():
        raise AppError(f"{service} temporarily unavailable", 503)
    else:
        raise AppError(f"Error with {service}", 502)

# Context manager for safe operations
from contextlib import asynccontextmanager

@asynccontextmanager
async def safe_operation(operation_name: str):
    """Context manager for performing operations safely"""
    try:
        logger.info(f"Starting operation: {operation_name}")
        yield
        logger.info(f"Completed operation: {operation_name}")
    except Exception as e:
        logger.error(f"Operation failed: {operation_name} - {str(e)}", exc_info=True)
        raise

# Health check for readiness during shutdown
class HealthCheckDuringShutdown:
    """Health check that considers shutdown state"""
    
    def __init__(self):
        self.ready_for_shutdown = False
    
    async def readiness_check(self):
        """Check if the app is ready to shut down"""
        # During graceful shutdown, we might want to check if we're ready
        # to stop accepting new requests
        if shutdown_manager.shutdown_requested:
            # Check if we're ready to shut down (e.g., no active long-running tasks)
            return len(shutdown_manager.active_tasks) == 0
        return True

# Example usage in main app setup
def setup_error_handling_and_shutdown(app: FastAPI):
    """Setup error handling and graceful shutdown for the app"""
    # Add error tracking middleware
    app.add_middleware(ErrorTrackingMiddleware)
    
    # Register exception handlers
    register_exception_handlers(app)
    
    # Setup signal handlers
    setup_signal_handlers()
    
    # Add shutdown manager to app state
    @app.on_event("startup")
    async def startup_event():
        logger.info("Application started")
    
    @app.on_event("shutdown")
    async def shutdown_event():
        await shutdown_manager.shutdown()

if __name__ == "__main__":
    # Example of how to use the error handling system
    import uvicorn
    from fastapi import FastAPI
    
    app = FastAPI()
    
    # Setup error handling and shutdown
    setup_error_handling_and_shutdown(app)
    
    @app.get("/")
    async def root():
        return {"message": "Hello World"}
    
    @app.get("/error-test")
    async def test_error():
        raise ValueError("This is a test error")
    
    @app.get("/shutdown-test")
    async def test_shutdown():
        shutdown_manager.request_shutdown()
        return {"message": "Shutdown initiated"}
    
    # Run the app
    # uvicorn.run(app, host="0.0.0.0", port=8000)