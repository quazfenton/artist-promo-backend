"""Proxy management for scrapers"""
import asyncio
import random
from typing import Optional, List
import aiohttp
import logging

logger = logging.getLogger(__name__)

class ProxyManager:
    def __init__(self, proxy_list: List[str] = None):
        # Default proxy list - in production, you'd load from a service
        self.proxy_list = proxy_list or [
            # These are example proxies - in production, use a proxy service
        ]
        self.active_proxies = self.proxy_list.copy()
        self.failed_proxies = []
        self.current_index = 0

    async def get_proxy(self) -> Optional[str]:
        """Get a working proxy from the list"""
        if not self.active_proxies:
            # If all proxies failed, reset the list
            self._reset_proxies()
            if not self.active_proxies:
                logger.warning("No proxies available, proceeding without proxy")
                return None

        # Round-robin selection
        proxy = self.active_proxies[self.current_index % len(self.active_proxies)]
        self.current_index += 1
        
        # Test the proxy before returning
        if await self._test_proxy(proxy):
            return proxy
        else:
            # Mark proxy as failed and try another
            self._mark_proxy_failed(proxy)
            return await self.get_proxy()  # Recursive call to get next proxy

    def get_proxy_sync(self) -> Optional[str]:
        """Sync version of get_proxy"""
        if not self.active_proxies:
            self._reset_proxies()
            if not self.active_proxies:
                logger.warning("No proxies available, proceeding without proxy")
                return None

        proxy = self.active_proxies[self.current_index % len(self.active_proxies)]
        self.current_index += 1
        
        # For sync, we'll just return the proxy without testing
        # In a real implementation, you'd want to test it
        return proxy

    async def _test_proxy(self, proxy: str) -> bool:
        """Test if a proxy is working"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "http://httpbin.org/ip",
                    proxy=proxy,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        logger.info(f"Proxy {proxy} is working")
                        return True
        except Exception as e:
            logger.warning(f"Proxy {proxy} failed test: {e}")
            return False
        return False

    def _mark_proxy_failed(self, proxy: str):
        """Mark a proxy as failed"""
        if proxy in self.active_proxies:
            self.active_proxies.remove(proxy)
            self.failed_proxies.append(proxy)
            logger.info(f"Marked proxy {proxy} as failed")

    def _reset_proxies(self):
        """Reset failed proxies back to active"""
        self.active_proxies.extend(self.failed_proxies)
        self.failed_proxies = []
        logger.info("Reset proxy list")

    def add_proxy(self, proxy: str):
        """Add a new proxy to the list"""
        if proxy not in self.proxy_list:
            self.proxy_list.append(proxy)
            self.active_proxies.append(proxy)
            logger.info(f"Added new proxy: {proxy}")

    def remove_proxy(self, proxy: str):
        """Remove a proxy from the list"""
        if proxy in self.proxy_list:
            self.proxy_list.remove(proxy)
            if proxy in self.active_proxies:
                self.active_proxies.remove(proxy)
            if proxy in self.failed_proxies:
                self.failed_proxies.remove(proxy)
            logger.info(f"Removed proxy: {proxy}")