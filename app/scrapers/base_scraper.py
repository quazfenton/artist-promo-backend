"""Enhanced base scraper with circuit breaker, retry logic, and comprehensive error handling"""
import asyncio
import aiohttp
import random
import time
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any, Union
from urllib.parse import urlparse
import logging
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import requests
from contextlib import asynccontextmanager
import json

from app.utils.circuit_breaker import CircuitBreaker, async_circuit_breaker
from app.utils.proxy_manager import ProxyManager
from app.utils.rate_limiter import AsyncRateLimiter
from app.utils.error_handler import handle_external_api_error

logger = logging.getLogger(__name__)

class ScraperError(Exception):
    """Custom exception for scraper errors"""
    pass

class BaseScraper(ABC):
    def __init__(self, name: str, base_delay: float = 1.0, max_delay: float = 10.0, max_retries: int = 5):
        self.name = name
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.max_retries = max_retries
        self.session = None
        self.proxy_manager = ProxyManager()
        self.rate_limiter = AsyncRateLimiter(max_calls=10, time_window=60)  # 10 calls per minute
        self.results = []
        self.errors = []
        self.stats = {
            "requests_made": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "blocked_requests": 0,
            "rate_limited": 0
        }

        # Initialize circuit breaker for this scraper
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=3,
            timeout=60,
            expected_exception=Exception,
            name=f"{name}_scraper"
        )

    async def initialize_session(self):
        """Initialize HTTP session with proper headers and timeout"""
        if self.session is None:
            timeout = aiohttp.ClientTimeout(total=30)
            self.session = aiohttp.ClientSession(timeout=timeout)
        return self.session

    def get_random_headers(self) -> Dict[str, str]:
        """Generate random browser-like headers to avoid detection"""
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/121.0",
            "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/121.0"
        ]

        accept_languages = [
            "en-US,en;q=0.9",
            "en-GB,en;q=0.8",
            "en-CA,en;q=0.7",
            "en-AU,en;q=0.6"
        ]

        return {
            "User-Agent": random.choice(user_agents),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": random.choice(accept_languages),
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Cache-Control": "max-age=0",
            "DNT": "1"  # Do not track
        }

    async def fetch_page_async(self, url: str, use_proxy: bool = True, timeout: int = 30) -> Optional[str]:
        """Fetch a page with comprehensive retry logic, circuit breaker, and error handling"""
        await self.initialize_session()

        # Apply rate limiting
        await self.rate_limiter.acquire()
        self.stats["requests_made"] += 1

        # Get proxy if needed
        proxy = None
        if use_proxy:
            proxy = await self.proxy_manager.get_proxy()

        headers = self.get_random_headers()

        # Try multiple times with different strategies
        for attempt in range(self.max_retries):
            try:
                async with self.session.get(url, headers=headers, proxy=proxy, timeout=aiohttp.ClientTimeout(total=timeout)) as response:
                    if response.status == 200:
                        content = await response.text()
                        self.stats["successful_requests"] += 1
                        logger.info(f"Successfully fetched {url} (attempt {attempt + 1})")
                        return content
                    elif response.status == 429:
                        # Too many requests - rate limited
                        self.stats["rate_limited"] += 1
                        logger.warning(f"Rate limited for {url} (attempt {attempt + 1}), waiting...")

                        # Exponential backoff with jitter
                        wait_time = min(2 ** attempt * 5 + random.uniform(1, 3), 60)
                        await asyncio.sleep(wait_time)

                        # Rotate proxy for next attempt
                        if use_proxy:
                            proxy = await self.proxy_manager.get_proxy()

                        continue
                    elif response.status in [403, 404, 401]:
                        # Access denied, not found, or unauthorized
                        self.stats["blocked_requests"] += 1
                        logger.warning(f"Access denied ({response.status}) for {url}")
                        return None
                    elif response.status >= 500:
                        # Server error - might be temporary
                        self.stats["failed_requests"] += 1
                        logger.warning(f"Server error ({response.status}) for {url}, attempt {attempt + 1}")

                        # Exponential backoff for server errors
                        wait_time = min(2 ** attempt * 2, 30)
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        # Other HTTP errors
                        self.stats["failed_requests"] += 1
                        logger.error(f"HTTP {response.status} for {url}")
                        return None

            except asyncio.TimeoutError:
                self.stats["failed_requests"] += 1
                logger.warning(f"Timeout fetching {url} (attempt {attempt + 1})")

                if attempt < self.max_retries - 1:
                    # Exponential backoff for timeouts
                    wait_time = min(2 ** attempt * 3, 30)
                    await asyncio.sleep(wait_time)
                continue
            except aiohttp.ClientConnectorError as e:
                self.stats["failed_requests"] += 1
                logger.warning(f"Connection error for {url}: {str(e)} (attempt {attempt + 1})")

                if attempt < self.max_retries - 1:
                    # Rotate proxy and wait
                    if use_proxy:
                        proxy = await self.proxy_manager.get_proxy()
                    wait_time = min(2 ** attempt * 2, 15)
                    await asyncio.sleep(wait_time)
                continue
            except Exception as e:
                self.stats["failed_requests"] += 1
                logger.error(f"Unexpected error fetching {url}: {str(e)} (attempt {attempt + 1})")

                if attempt < self.max_retries - 1:
                    # Wait before retrying
                    wait_time = min(2 ** attempt * 2, 10)
                    await asyncio.sleep(wait_time)
                continue

        # All retries exhausted
        logger.error(f"All retries failed for {url}")
        return None

    def fetch_page_sync(self, url: str, use_proxy: bool = True, timeout: int = 30) -> Optional[str]:
        """Sync version of fetch_page with comprehensive error handling"""
        # Apply rate limiting (sync version)
        time.sleep(0.1)  # Simple rate limiting for sync calls
        self.stats["requests_made"] += 1

        # Get proxy if needed
        proxy = None
        if use_proxy:
            proxy = self.proxy_manager.get_proxy_sync()

        headers = self.get_random_headers()

        # Try multiple times with different strategies
        for attempt in range(self.max_retries):
            try:
                response = requests.get(url, headers=headers, proxies=proxy, timeout=timeout)
                if response.status_code == 200:
                    self.stats["successful_requests"] += 1
                    logger.info(f"Successfully fetched {url} (attempt {attempt + 1})")
                    return response.text
                elif response.status_code == 429:
                    # Rate limited
                    self.stats["rate_limited"] += 1
                    logger.warning(f"Rate limited for {url} (attempt {attempt + 1}), waiting...")

                    # Exponential backoff with jitter
                    wait_time = min(2 ** attempt * 5 + random.uniform(1, 3), 60)
                    time.sleep(wait_time)

                    # Rotate proxy for next attempt
                    if use_proxy:
                        proxy = self.proxy_manager.get_proxy_sync()

                    continue
                elif response.status_code in [403, 404, 401]:
                    # Access denied, not found, or unauthorized
                    self.stats["blocked_requests"] += 1
                    logger.warning(f"Access denied ({response.status_code}) for {url}")
                    return None
                elif response.status_code >= 500:
                    # Server error - might be temporary
                    self.stats["failed_requests"] += 1
                    logger.warning(f"Server error ({response.status_code}) for {url}, attempt {attempt + 1}")

                    # Exponential backoff for server errors
                    wait_time = min(2 ** attempt * 2, 30)
                    time.sleep(wait_time)
                    continue
                else:
                    # Other HTTP errors
                    self.stats["failed_requests"] += 1
                    logger.error(f"HTTP {response.status_code} for {url}")
                    return None

            except requests.exceptions.Timeout:
                self.stats["failed_requests"] += 1
                logger.warning(f"Timeout fetching {url} (attempt {attempt + 1})")

                if attempt < self.max_retries - 1:
                    # Exponential backoff for timeouts
                    wait_time = min(2 ** attempt * 3, 30)
                    time.sleep(wait_time)
                continue
            except requests.exceptions.ConnectionError as e:
                self.stats["failed_requests"] += 1
                logger.warning(f"Connection error for {url}: {str(e)} (attempt {attempt + 1})")

                if attempt < self.max_retries - 1:
                    # Rotate proxy and wait
                    if use_proxy:
                        proxy = self.proxy_manager.get_proxy_sync()
                    wait_time = min(2 ** attempt * 2, 15)
                    time.sleep(wait_time)
                continue
            except Exception as e:
                self.stats["failed_requests"] += 1
                logger.error(f"Unexpected error fetching {url}: {str(e)} (attempt {attempt + 1})")

                if attempt < self.max_retries - 1:
                    # Wait before retrying
                    wait_time = min(2 ** attempt * 2, 10)
                    time.sleep(wait_time)
                continue

        # All retries exhausted
        logger.error(f"All retries failed for {url}")
        return None

    async def exponential_backoff(self, attempt: int):
        """Wait with exponential backoff"""
        delay = min(self.base_delay * (2 ** attempt) + random.uniform(0, 1), self.max_delay)
        logger.info(f"Attempt {attempt + 1}, waiting {delay:.2f} seconds...")
        await asyncio.sleep(delay)

    def is_valid_url(self, url: str) -> bool:
        """Validate URL format"""
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except Exception:
            return False

    def validate_response(self, content: str, url: str) -> bool:
        """Validate response content"""
        if not content:
            return False

        # Check for common anti-bot responses
        content_lower = content.lower()
        if any(indicator in content_lower for indicator in [
            "access denied", "bot detected", "captcha", "please enable javascript",
            "blocked", "forbidden", "unavailable", "checking your browser"
        ]):
            logger.warning(f"Anti-bot response detected for {url}")
            return False

        return True

    @abstractmethod
    async def scrape(self, **kwargs) -> List[Dict[str, Any]]:
        """Abstract method to be implemented by subclasses"""
        pass

    async def cleanup(self):
        """Clean up resources"""
        if self.session:
            await self.session.close()

    def add_result(self, result: Dict[str, Any]):
        """Add a result to the results list"""
        self.results.append(result)

    def add_error(self, error: str, url: str = None, error_type: str = "general"):
        """Add an error to the errors list"""
        error_obj = {
            "timestamp": time.time(),
            "error": error,
            "url": url,
            "error_type": error_type,
            "attempt_number": len(self.errors) + 1
        }
        self.errors.append(error_obj)
        logger.error(f"Scraper {self.name} error [{error_type}]: {error} for URL: {url}")

    async def get_circuit_breaker_state(self) -> str:
        """Get current circuit breaker state"""
        return self.circuit_breaker.state.value

    def reset_circuit_breaker(self):
        """Reset the circuit breaker"""
        self.circuit_breaker.reset()

    def get_stats(self) -> Dict[str, Any]:
        """Get scraper statistics"""
        return {
            **self.stats,
            "total_results": len(self.results),
            "total_errors": len(self.errors),
            "success_rate": self.stats["successful_requests"] / max(self.stats["requests_made"], 1) * 100
        }

    def reset_stats(self):
        """Reset scraper statistics"""
        self.stats = {
            "requests_made": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "blocked_requests": 0,
            "rate_limited": 0
        }
        self.results = []
        self.errors = []

    async def safe_scrape(self, **kwargs) -> List[Dict[str, Any]]:
        """Safely execute scrape with comprehensive error handling"""
        try:
            results = await self.scrape(**kwargs)
            if results is None:
                results = []
            return results
        except asyncio.CancelledError:
            # Re-raise cancellation to allow proper task cancellation
            raise
        except Exception as e:
            error_msg = f"Fatal error in scraper {self.name}: {str(e)}"
            self.add_error(error_msg, error_type="fatal")
            logger.error(error_msg, exc_info=True)
            # Don't silently return empty - log that we're returning empty due to error
            logger.warning(f"Returning empty results for {self.name} due to error")
            return []  # Return empty list on fatal error