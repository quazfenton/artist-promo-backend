"""
Base scraper class with enhanced reliability and anti-bot measures
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from datetime import datetime
from loguru import logger
import time
import random
import asyncio
import aiohttp
from tenacity import retry, stop_after_attempt, wait_exponential
import requests
from bs4 import BeautifulSoup
import re

class ProxyManager:
    """Manage proxy rotation"""
    
    def __init__(self):
        self.proxies = self._load_proxies()
        self.current_index = 0
    
    def _load_proxies(self) -> List[str]:
        """Load proxy list from environment or file"""
        import os
        proxy_list = os.getenv("PROXY_LIST", "").split(",")
        return [p.strip() for p in proxy_list if p.strip()]
    
    def get_proxy(self) -> Optional[str]:
        """Get next proxy in rotation"""
        if not self.proxies:
            return None
        
        proxy = self.proxies[self.current_index]
        self.current_index = (self.current_index + 1) % len(self.proxies)
        return proxy

class UserAgentRotator:
    """Rotate user agents to avoid detection"""
    
    def __init__(self):
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        ]
    
    def get_random_user_agent(self) -> str:
        """Get random user agent"""
        return random.choice(self.user_agents)

class RateLimiter:
    """Rate limiting for requests"""
    
    def __init__(self, requests_per_second: float = 2.0):
        self.requests_per_second = requests_per_second
        self.last_request_time = 0
    
    async def wait(self):
        """Wait if necessary to respect rate limit"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        min_interval = 1.0 / self.requests_per_second
        
        if time_since_last < min_interval:
            wait_time = min_interval - time_since_last
            await asyncio.sleep(wait_time)
        
        self.last_request_time = time.time()

class BaseScraper(ABC):
    """Enhanced base class for all scrapers"""
    
    def __init__(self, name: str):
        self.name = name
        self.proxy_manager = ProxyManager()
        self.user_agent_rotator = UserAgentRotator()
        self.rate_limiter = RateLimiter()
        self.results = []
        self.errors = []
        self.session = None
    
    @abstractmethod
    def scrape(self, *args, **kwargs) -> List[Dict]:
        """Main scraping method - must be implemented by subclasses"""
        pass
    
    async def __aenter__(self):
        """Async context manager entry"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            connector=aiohttp.TCPConnector(limit=10)
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def fetch_page_async(self, url: str, headers: Optional[Dict] = None) -> Optional[str]:
        """Fetch page with retry logic and anti-bot measures"""
        
        await self.rate_limiter.wait()
        
        # Prepare headers with random user agent
        request_headers = {
            'User-Agent': self.user_agent_rotator.get_random_user_agent(),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        if headers:
            request_headers.update(headers)
        
        # Get proxy
        proxy = self.proxy_manager.get_proxy()
        
        try:
            logger.info(f"[{self.name}] Fetching: {url}")
            
            async with self.session.get(
                url, 
                headers=request_headers,
                proxy=proxy,
                ssl=False
            ) as response:
                if response.status == 200:
                    content = await response.text()
                    # Random delay to appear more human
                    await asyncio.sleep(random.uniform(0.5, 2.0))
                    return content
                elif response.status == 429:
                    # Rate limited - wait longer
                    logger.warning(f"[{self.name}] Rate limited on {url}")
                    await asyncio.sleep(random.uniform(5, 15))
                    raise Exception(f"Rate limited: {response.status}")
                else:
                    raise Exception(f"HTTP {response.status}")
                    
        except Exception as e:
            logger.error(f"[{self.name}] Error fetching {url}: {str(e)}")
            self.errors.append({"url": url, "error": str(e)})
            raise
    
    def fetch_page_sync(self, url: str, headers: Optional[Dict] = None) -> Optional[requests.Response]:
        """Synchronous fetch with retry logic"""
        
        request_headers = {
            'User-Agent': self.user_agent_rotator.get_random_user_agent(),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        }
        
        if headers:
            request_headers.update(headers)
        
        proxy = self.proxy_manager.get_proxy()
        proxies = {'http': proxy, 'https': proxy} if proxy else None
        
        try:
            # Rate limiting for sync requests
            time.sleep(1.0 / self.rate_limiter.requests_per_second)
            
            logger.info(f"[{self.name}] Fetching: {url}")
            response = requests.get(
                url, 
                headers=request_headers, 
                proxies=proxies,
                timeout=30,
                verify=False
            )
            response.raise_for_status()
            
            # Random delay
            time.sleep(random.uniform(0.5, 2.0))
            return response
            
        except Exception as e:
            logger.error(f"[{self.name}] Error fetching {url}: {str(e)}")
            self.errors.append({"url": url, "error": str(e)})
            raise
    
    def parse_html(self, html_content: str) -> BeautifulSoup:
        """Parse HTML content"""
        return BeautifulSoup(html_content, 'lxml')
    
    def extract_emails(self, text: str) -> List[str]:
        """Extract email addresses from text"""
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = re.findall(email_pattern, text)
        
        # Filter out common false positives
        filtered_emails = []
        for email in emails:
            if not any(skip in email.lower() for skip in ['noreply', 'no-reply', 'example.com', 'test.com']):
                filtered_emails.append(email)
        
        return list(set(filtered_emails))  # Remove duplicates
    
    def extract_social_handles(self, text: str, soup: BeautifulSoup) -> Dict[str, str]:
        """Extract social media handles"""
        handles = {}
        
        # Instagram
        instagram_pattern = r'@([a-zA-Z0-9._]{1,30})'
        instagram_matches = re.findall(instagram_pattern, text)
        if instagram_matches:
            handles['instagram'] = instagram_matches[0]
        
        # Twitter
        twitter_links = soup.find_all('a', href=re.compile(r'twitter\.com/'))
        if twitter_links:
            twitter_url = twitter_links[0]['href']
            twitter_handle = twitter_url.split('/')[-1]
            handles['twitter'] = twitter_handle
        
        # LinkedIn
        linkedin_links = soup.find_all('a', href=re.compile(r'linkedin\.com/'))
        if linkedin_links:
            handles['linkedin'] = linkedin_links[0]['href']
        
        return handles
    
    def save_result(self, result: Dict):
        """Save scraping result"""
        result['scraped_at'] = datetime.utcnow().isoformat()
        result['scraper_name'] = self.name
        self.results.append(result)
        logger.debug(f"[{self.name}] Saved result: {result.get('url', 'N/A')}")
    
    def get_results(self) -> List[Dict]:
        """Get all scraping results"""
        return self.results
    
    def get_errors(self) -> List[Dict]:
        """Get all scraping errors"""
        return self.errors
    
    def get_stats(self) -> Dict:
        """Get scraping statistics"""
        return {
            "scraper_name": self.name,
            "total_results": len(self.results),
            "total_errors": len(self.errors),
            "success_rate": len(self.results) / (len(self.results) + len(self.errors)) if (len(self.results) + len(self.errors)) > 0 else 0
        }
    
    def _random_delay(self, min_seconds: float = 0.5, max_seconds: float = 2.0):
        """Add random delay to appear more human"""
        delay = random.uniform(min_seconds, max_seconds)
        time.sleep(delay)
        """Extract email addresses from text"""
        import re
        pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        return list(set(re.findall(pattern, text)))
    
    def extract_social_handles(self, soup: BeautifulSoup) -> Dict[str, str]:
        """Extract social media handles from page"""
        socials = {}
        
        # Instagram
        instagram_links = soup.find_all('a', href=lambda x: x and 'instagram.com' in x)
        if instagram_links:
            socials['instagram'] = instagram_links[0]['href']
        
        # Twitter
        twitter_links = soup.find_all('a', href=lambda x: x and ('twitter.com' in x or 'x.com' in x))
        if twitter_links:
            socials['twitter'] = twitter_links[0]['href']
        
        # LinkedIn
        linkedin_links = soup.find_all('a', href=lambda x: x and 'linkedin.com' in x)
        if linkedin_links:
            socials['linkedin'] = linkedin_links[0]['href']
        
        return socials
    
    def _random_delay(self, min_delay: float = 0.5, max_delay: float = 2.0):
        """Add random delay to avoid rate limiting"""
        time.sleep(random.uniform(min_delay, max_delay))
    
    def save_result(self, result: Dict):
        """Save a result"""
        result['scraped_at'] = datetime.utcnow().isoformat()
        result['scraper_name'] = self.name
        self.results.append(result)
    
    def get_results(self) -> List[Dict]:
        """Get all results"""
        return self.results
    
    def get_stats(self) -> Dict:
        """Get scraping statistics"""
        return {
            "scraper_name": self.name,
            "total_results": len(self.results),
            "total_errors": len(self.errors),
            "success_rate": len(self.results) / (len(self.results) + len(self.errors)) if (len(self.results) + len(self.errors)) > 0 else 0
        }
