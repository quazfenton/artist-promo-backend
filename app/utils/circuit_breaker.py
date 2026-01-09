"""Circuit breaker pattern implementation for external API calls"""
import asyncio
import time
import enum
from typing import Callable, Any, Optional, Type
from functools import wraps
import logging

logger = logging.getLogger(__name__)

class CircuitState(enum.Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Tripped, requests blocked
    HALF_OPEN = "half_open" # Testing if failure condition is resolved

class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: int = 5,
        timeout: int = 60,  # seconds to stay open
        expected_exception: Type[Exception] = Exception,
        name: str = "default"
    ):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.expected_exception = expected_exception
        self.name = name
        
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time = None
        self._success_count = 0  # For half-open state testing

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection"""
        if self._state == CircuitState.OPEN:
            if self._should_trip_to_half_open():
                self._state = CircuitState.HALF_OPEN
                logger.info(f"Circuit breaker {self.name} transitioning to HALF_OPEN")
            else:
                raise Exception(f"Circuit breaker {self.name} is OPEN. Call failed.")
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            raise e

    async def async_call(self, func, *args, **kwargs) -> Any:
        """Execute async function with circuit breaker protection"""
        if self._state == CircuitState.OPEN:
            if self._should_trip_to_half_open():
                self._state = CircuitState.HALF_OPEN
                logger.info(f"Circuit breaker {self.name} transitioning to HALF_OPEN")
            else:
                raise Exception(f"Circuit breaker {self.name} is OPEN. Call failed.")
        
        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            raise e

    def _on_success(self):
        """Handle successful call"""
        self._failure_count = 0
        self._last_failure_time = None
        
        if self._state == CircuitState.HALF_OPEN:
            self._success_count += 1
            # If we have enough successes in half-open state, close the circuit
            if self._success_count >= 2:  # Allow 2 consecutive successes
                self._close_circuit()
        else:
            self._state = CircuitState.CLOSED

    def _on_failure(self):
        """Handle failed call"""
        self._failure_count += 1
        self._last_failure_time = time.time()
        
        if self._failure_count >= self.failure_threshold:
            self._open_circuit()

    def _open_circuit(self):
        """Open the circuit (trip the breaker)"""
        self._state = CircuitState.OPEN
        logger.warning(f"Circuit breaker {self.name} TRIPPED. State: OPEN")

    def _close_circuit(self):
        """Close the circuit (reset the breaker)"""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = None
        logger.info(f"Circuit breaker {self.name} RESET. State: CLOSED")

    def _should_trip_to_half_open(self) -> bool:
        """Check if enough time has passed to try closing the circuit"""
        if self._last_failure_time is None:
            return False
        return time.time() - self._last_failure_time >= self.timeout

    @property
    def state(self) -> CircuitState:
        """Get current circuit state"""
        return self._state

    def reset(self):
        """Manually reset the circuit breaker"""
        self._close_circuit()

# Decorator for synchronous functions
def circuit_breaker(
    failure_threshold: int = 5,
    timeout: int = 60,
    expected_exception: Type[Exception] = Exception,
    name: str = "default"
):
    """Circuit breaker decorator for sync functions"""
    def decorator(func):
        cb = CircuitBreaker(
            failure_threshold=failure_threshold,
            timeout=timeout,
            expected_exception=expected_exception,
            name=name or func.__name__
        )
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            return cb.call(func, *args, **kwargs)
        
        # Attach circuit breaker instance to function for introspection
        wrapper.circuit_breaker = cb
        return wrapper
    
    return decorator

# Decorator for asynchronous functions
def async_circuit_breaker(
    failure_threshold: int = 5,
    timeout: int = 60,
    expected_exception: Type[Exception] = Exception,
    name: str = "default"
):
    """Circuit breaker decorator for async functions"""
    def decorator(func):
        cb = CircuitBreaker(
            failure_threshold=failure_threshold,
            timeout=timeout,
            expected_exception=expected_exception,
            name=name or func.__name__
        )
        
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await cb.async_call(func, *args, **kwargs)
        
        # Attach circuit breaker instance to function for introspection
        wrapper.circuit_breaker = cb
        return wrapper
    
    return decorator

# Pre-configured circuit breakers for common use cases
class CircuitBreakerRegistry:
    """Registry of commonly used circuit breakers"""
    
    # For external API calls
    external_api = circuit_breaker(
        failure_threshold=3,
        timeout=30,
        expected_exception=Exception,
        name="external_api"
    )
    
    # For database operations
    database = circuit_breaker(
        failure_threshold=5,
        timeout=60,
        expected_exception=Exception,
        name="database"
    )
    
    # For Redis/cache operations
    cache = circuit_breaker(
        failure_threshold=5,
        timeout=30,
        expected_exception=Exception,
        name="cache"
    )
    
    # For email/SMS services
    notification = circuit_breaker(
        failure_threshold=3,
        timeout=120,
        expected_exception=Exception,
        name="notification"
    )

# Example usage functions
async def make_external_api_call(url: str, **kwargs) -> dict:
    """Example external API call wrapped with circuit breaker"""
    import aiohttp
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, **kwargs) as response:
            return await response.json()

# Wrap the function with circuit breaker
cb_make_external_api_call = async_circuit_breaker(
    failure_threshold=3,
    timeout=30,
    expected_exception=aiohttp.ClientError,
    name="external_api_call"
)(make_external_api_call)

# Context manager for manual circuit breaker usage
class CircuitBreakerContext:
    """Context manager for manual circuit breaker usage"""
    def __init__(self, circuit_breaker: CircuitBreaker):
        self.cb = circuit_breaker
    
    async def __aenter__(self):
        if self.cb._state == CircuitState.OPEN:
            if self.cb._should_trip_to_half_open():
                self.cb._state = CircuitState.HALF_OPEN
            else:
                raise Exception(f"Circuit breaker is OPEN. Operation blocked.")
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type and issubclass(exc_type, self.cb.expected_exception):
            self.cb._on_failure()
        else:
            self.cb._on_success()
        return False  # Don't suppress exceptions

if __name__ == "__main__":
    # Example usage
    @circuit_breaker(failure_threshold=2, timeout=10, name="test_api")
    def failing_function():
        raise Exception("Simulated failure")
    
    # This will trip the circuit breaker after 2 failures
    for i in range(5):
        try:
            failing_function()
        except Exception as e:
            print(f"Call {i+1} failed: {e}")
        
        # Wait a bit between calls
        time.sleep(0.1)
    
    # Check circuit state
    print(f"Circuit state: {failing_function.circuit_breaker.state}")