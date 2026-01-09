"""Asynchronous rate limiter"""
import asyncio
import time
from collections import deque
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class AsyncRateLimiter:
    def __init__(self, max_calls: int, time_window: int):
        """
        Initialize rate limiter
        :param max_calls: Maximum number of calls allowed
        :param time_window: Time window in seconds
        """
        self.max_calls = max_calls
        self.time_window = time_window
        self.calls = deque()
        self._lock = asyncio.Lock()

    async def acquire(self):
        """Acquire a permit, waiting if necessary"""
        async with self._lock:
            now = time.time()
            
            # Remove calls that are outside the time window
            while self.calls and self.calls[0] <= now - self.time_window:
                self.calls.popleft()
            
            # If we've reached the limit, wait until we can proceed
            if len(self.calls) >= self.max_calls:
                sleep_time = self.time_window - (now - self.calls[0])
                if sleep_time > 0:
                    logger.warning(f"Rate limit reached, sleeping for {sleep_time:.2f}s")
                    await asyncio.sleep(sleep_time)
                    
                    # After sleeping, re-check the lock and time
                    now = time.time()
                    while self.calls and self.calls[0] <= now - self.time_window:
                        self.calls.popleft()
            
            # Add current call
            self.calls.append(now)

    async def acquire_timeout(self, timeout: float) -> bool:
        """
        Acquire a permit with timeout
        :param timeout: Maximum time to wait in seconds
        :return: True if permit acquired, False if timed out
        """
        try:
            await asyncio.wait_for(self.acquire(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            logger.warning(f"Rate limiter timeout after {timeout}s")
            return False

    def get_stats(self) -> dict:
        """Get current rate limiter statistics"""
        now = time.time()
        # Remove expired calls
        while self.calls and self.calls[0] <= now - self.time_window:
            self.calls.popleft()
        
        return {
            "current_calls": len(self.calls),
            "max_calls": self.max_calls,
            "time_window": self.time_window,
            "available_calls": max(0, self.max_calls - len(self.calls)),
            "reset_in": self.time_window - (now - self.calls[0]) if self.calls else 0
        }

# Decorator for rate limiting functions
def rate_limit(max_calls: int, time_window: int):
    """Rate limit decorator for async functions"""
    limiter = AsyncRateLimiter(max_calls, time_window)
    
    def decorator(func):
        import functools
        
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            await limiter.acquire()
            return await func(*args, **kwargs)
        
        # Attach limiter for introspection
        wrapper.limiter = limiter
        return wrapper
    
    return decorator

# Example usage
if __name__ == "__main__":
    import asyncio
    
    # Example: Limit to 5 calls per 10 seconds
    rl = AsyncRateLimiter(max_calls=5, time_window=10)
    
    async def example_call(i):
        await rl.acquire()
        print(f"Call {i} executed at {time.time()}")
        await asyncio.sleep(0.1)  # Simulate work
    
    async def main():
        tasks = [example_call(i) for i in range(10)]
        await asyncio.gather(*tasks)
        
        print("Stats:", rl.get_stats())
    
    # Run example
    # asyncio.run(main())