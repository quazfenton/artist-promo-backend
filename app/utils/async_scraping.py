"""
Async scraping and enrichment executor
"""
import asyncio
import aiohttp
import random
from typing import List, Dict, Any, Callable, Optional
from urllib.parse import urlparse
import time
from app.utils.email_canonicalization import check_email_domain_reputation
from app.utils.link_in_bio_resolver import resolve_link_tree

# Semaphore to limit concurrent requests
SEM = asyncio.Semaphore(5)

# Common headers to avoid blocking
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
}

# Mirror instances for different platforms
NITTER_INSTANCES = [
    "https://nitter.net",
    "https://nitter.snopyta.org", 
    "https://nitter.unixfox.eu",
    "https://nitter.nixnet.services",
    "https://nitter.1d4.us"
]

INVIDIOUS_INSTANCES = [
    "https://yewtu.be",
    "https://vid.puffyan.us",
    "https://invidious.io",
    "https://inv.riverside.rocks",
    "https://ytprivate.com"
]

IMGUR_INSTANCES = [
    "https://imginn.com",
    "https://picuki.com",
    "https://www.instadp.com"
]

PROXITOK_INSTANCES = [
    "https://proxitok.pabloferreiro.es",
    "https://tok.habedieeh.re",
    "https://tiktok-proxy.404.best"
]

LIBREDDIT_INSTANCES = [
    "https://libreddit.kavin.rocks",
    "https://lr.riverside.rocks",
    "https://reddit.invak.id"
]

async def fetch_async(session: aiohttp.ClientSession, url: str, **kwargs) -> str:
    """
    Async fetch with semaphore limiting
    """
    async with SEM:
        try:
            timeout = aiohttp.ClientTimeout(total=15)
            async with session.get(url, timeout=timeout, **kwargs) as response:
                response.raise_for_status()
                return await response.text()
        except Exception as e:
            print(f"Error fetching {url}: {str(e)}")
            return ""

async def fetch_json_async(session: aiohttp.ClientSession, url: str, **kwargs) -> Dict[str, Any]:
    """
    Async fetch JSON with error handling
    """
    async with SEM:
        try:
            timeout = aiohttp.ClientTimeout(total=15)
            async with session.get(url, timeout=timeout, **kwargs) as response:
                response.raise_for_status()
                return await response.json()
        except Exception as e:
            print(f"Error fetching JSON from {url}: {str(e)}")
            return {}

def get_random_instance(instances: List[str]) -> str:
    """
    Get a random instance from a list of mirrors
    """
    return random.choice(instances)

async def scrape_nitter(username: str) -> Dict[str, Any]:
    """
    Scrape user data from Nitter (Twitter alternative)
    """
    base = get_random_instance(NITTER_INSTANCES)
    url = f"{base}/{username}"
    
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        html = await fetch_async(session, url)
        
        if not html:
            return {"error": f"Failed to fetch from {url}"}
        
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        
        # Extract bio
        bio_element = soup.select_one(".profile-bio")
        bio = bio_element.get_text(" ", strip=True) if bio_element else ""
        
        # Extract follower count
        follower_element = soup.select_one("li.followers .profile-stat-num")
        followers = 0
        if follower_element:
            followers_text = follower_element.get_text(strip=True)
            # Remove commas and convert to int
            cleaned_text = followers_text.replace(',', '')
            followers = int(cleaned_text) if cleaned_text.isdigit() else 0
        
        # Extract name
        name_element = soup.select_one(".profile-card-fullname")
        name = name_element.get_text(strip=True) if name_element else username
        
        # Extract external links
        links = []
        for link in soup.select(".profile-links a[href^='http']"):
            href = link.get('href')
            if href:
                links.append(href)
        
        # Extract emails from bio
        import re
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = list(set(re.findall(email_pattern, bio)))
        
        return {
            "platform": "twitter",
            "username": username,
            "name": name,
            "bio": bio,
            "emails": emails,
            "links": links,
            "follower_count": followers,
            "source": url
        }

async def scrape_invidious_channel(channel_id: str) -> Dict[str, Any]:
    """
    Scrape YouTube channel data from Invidious
    """
    base = get_random_instance(INVIDIOUS_INSTANCES)
    url = f"{base}/channel/{channel_id}/about"
    
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        html = await fetch_async(session, url)
        
        if not html:
            return {"error": f"Failed to fetch from {url}"}
        
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        
        # Extract channel about info
        about_element = soup.select_one(".channel-about")
        about_text = about_element.get_text(" ", strip=True) if about_element else ""
        
        # Extract subscriber count
        sub_count_element = soup.select_one(".subscriber-count")
        subscribers = 0
        if sub_count_element:
            sub_text = sub_count_element.get_text(strip=True)
            # Parse subscriber count (e.g., "1.2K subscribers" -> 1200)
            import re
            numbers = re.findall(r'[\d.]+', sub_text)
            if numbers:
                num = float(numbers[0])
                if 'K' in sub_text.upper():
                    num *= 1000
                elif 'M' in sub_text.upper():
                    num *= 1000000
                subscribers = int(num)
        
        # Extract external links
        links = []
        for link in soup.select("a[href^='http']"):
            href = link.get('href')
            if href:
                links.append(href)
        
        # Extract emails from about text
        import re
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = list(set(re.findall(email_pattern, about_text)))
        
        return {
            "platform": "youtube",
            "channel_id": channel_id,
            "about": about_text,
            "emails": emails,
            "links": links,
            "subscriber_count": subscribers,
            "source": url
        }

async def scrape_imginn(username: str) -> Dict[str, Any]:
    """
    Scrape Instagram profile from Imginn
    """
    url = f"https://imginn.com/{username}/"
    
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        html = await fetch_async(session, url)
        
        if not html:
            return {"error": f"Failed to fetch from {url}"}
        
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        
        # Extract bio
        bio_element = soup.select_one(".bio")
        bio = bio_element.get_text(" ", strip=True) if bio_element else ""
        
        # Extract follower count
        follower_element = soup.select_one(".followers .count")
        followers = 0
        if follower_element:
            followers_text = follower_element.get_text(strip=True)
            cleaned_text = followers_text.replace(',', '')
            followers = int(cleaned_text) if cleaned_text.isdigit() else 0
        
        # Extract name
        name_element = soup.select_one(".profile-name")
        name = name_element.get_text(strip=True) if name_element else username
        
        # Extract external link
        links = []
        external_link_element = soup.select_one("a[href^='http']")
        if external_link_element:
            href = external_link_element.get('href')
            if href:
                links.append(href)
        
        # Extract emails from bio
        import re
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = list(set(re.findall(email_pattern, bio)))
        
        return {
            "platform": "instagram",
            "username": username,
            "name": name,
            "bio": bio,
            "emails": emails,
            "links": links,
            "follower_count": followers,
            "source": url
        }

async def scrape_proxitok(username: str) -> Dict[str, Any]:
    """
    Scrape TikTok profile from ProxiTok
    """
    url = f"https://proxitok.pabloferreiro.es/@{username}"
    
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        html = await fetch_async(session, url)
        
        if not html:
            return {"error": f"Failed to fetch from {url}"}
        
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        
        # Extract bio
        bio_element = soup.select_one(".bio")
        bio = bio_element.get_text(" ", strip=True) if bio_element else ""
        
        # Extract follower count
        follower_element = soup.select_one(".followers .count")
        followers = 0
        if follower_element:
            followers_text = follower_element.get_text(strip=True)
            cleaned_text = followers_text.replace(',', '')
            followers = int(cleaned_text) if cleaned_text.isdigit() else 0
        
        # Extract name
        name_element = soup.select_one(".username")
        name = name_element.get_text(strip=True) if name_element else username
        
        # Extract external links
        links = []
        for link in soup.select("a[href^='http']"):
            href = link.get('href')
            if href:
                links.append(href)
        
        # Extract emails from bio
        import re
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = list(set(re.findall(email_pattern, bio)))
        
        return {
            "platform": "tiktok",
            "username": username,
            "name": name,
            "bio": bio,
            "emails": emails,
            "links": links,
            "follower_count": followers,
            "source": url
        }

async def scrape_libreddit_subreddit(subreddit: str, limit: int = 5) -> Dict[str, Any]:
    """
    Scrape subreddit from Libreddit
    """
    base = get_random_instance(LIBREDDIT_INSTANCES)
    url = f"{base}/r/{subreddit}"
    
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        html = await fetch_async(session, url)
        
        if not html:
            return {"error": f"Failed to fetch from {url}"}
        
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        
        # Extract posts
        posts = soup.select("div.post")[:limit]
        
        results = []
        for post in posts:
            text = post.get_text(" ", strip=True)[:500]  # Limit text length
            
            # Extract emails from post
            import re
            email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
            emails = list(set(re.findall(email_pattern, text)))
            
            if emails:
                results.append({
                    "text": text,
                    "emails": emails,
                    "source": url
                })
        
        return {
            "platform": "reddit",
            "subreddit": subreddit,
            "matches": results,
            "source": url
        }

async def run_async_tasks(tasks: List[Callable]) -> List[Any]:
    """
    Run multiple async tasks concurrently
    """
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        # Create coroutines for tasks that need session
        coros = []
        for task in tasks:
            if callable(task):
                # If task is a function that takes session, call it
                if task.__code__.co_argcount > 0:  # Check if function expects arguments
                    coros.append(task(session))
                else:
                    coros.append(task())
            else:
                coros.append(task)
        
        results = await asyncio.gather(*coros, return_exceptions=True)
        
        # Filter out exceptions
        processed_results = []
        for result in results:
            if isinstance(result, Exception):
                print(f"Task failed: {result}")
                processed_results.append({"error": str(result)})
            else:
                processed_results.append(result)
        
        return processed_results

async def scrape_all_platforms(handles: Dict[str, str]) -> List[Dict[str, Any]]:
    """
    Scrape all platforms concurrently based on provided handles
    """
    tasks = []
    
    if "twitter" in handles:
        tasks.append(lambda s: scrape_nitter(handles["twitter"]))
    
    if "youtube" in handles:
        tasks.append(lambda s: scrape_invidious_channel(handles["youtube"]))
    
    if "instagram" in handles:
        tasks.append(lambda s: scrape_imginn(handles["instagram"]))
    
    if "tiktok" in handles:
        tasks.append(lambda s: scrape_proxitok(handles["tiktok"]))
    
    if "reddit" in handles:
        tasks.append(lambda s: scrape_libreddit_subreddit(handles["reddit"]))
    
    if tasks:
        return await run_async_tasks(tasks)
    else:
        return []

async def enrich_contact_data(contact_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enrich contact data with additional information
    """
    enriched_data = contact_data.copy()
    
    # Add domain reputation checks
    if contact_data.get("emails"):
        domain_reputations = {}
        for email in contact_data["emails"]:
            domain_rep = check_email_domain_reputation(email)
            domain_reputations[email] = domain_rep
        enriched_data["domain_reputations"] = domain_reputations
    
    # Add link-in-bio resolution if available
    if contact_data.get("links"):
        bio_resolutions = []
        for link in contact_data["links"]:
            try:
                resolution = await resolve_link_tree(link, depth=2)
                bio_resolutions.append(resolution)
            except Exception as e:
                print(f"Error resolving link tree for {link}: {str(e)}")
        enriched_data["link_tree_resolutions"] = bio_resolutions
    
    # Add timestamp
    from datetime import datetime
    enriched_data["enrichment_timestamp"] = datetime.utcnow().isoformat()
    
    return enriched_data

async def run_enrichment_pipeline(contacts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Run enrichment pipeline on multiple contacts concurrently
    """
    tasks = [lambda s, c=c: enrich_contact_data(c) for c in contacts]
    return await run_async_tasks(tasks)

async def scrape_with_fallback(primary_url: str, fallback_urls: List[str]) -> Dict[str, Any]:
    """
    Scrape primary URL with fallbacks if it fails
    """
    urls_to_try = [primary_url] + fallback_urls
    
    for url in urls_to_try:
        try:
            async with aiohttp.ClientSession(headers=HEADERS) as session:
                html = await fetch_async(session, url)
                if html:
                    return {
                        "success": True,
                        "data": html,
                        "source": url,
                        "fallback_used": url != primary_url
                    }
        except Exception as e:
            print(f"Failed to fetch from {url}: {str(e)}")
            continue
    
    return {
        "success": False,
        "error": "All URLs failed",
        "source": primary_url,
        "fallback_used": False
    }

async def batch_scrape(urls: List[str], max_concurrent: int = 10) -> List[Dict[str, Any]]:
    """
    Batch scrape multiple URLs with controlled concurrency
    """
    # Create a new semaphore for this batch operation only
    batch_semaphore = asyncio.Semaphore(max_concurrent)

    async def fetch_with_semaphore(session, url):
        async with batch_semaphore:
            try:
                timeout = aiohttp.ClientTimeout(total=15)
                async with session.get(url, timeout=timeout) as response:
                    response.raise_for_status()
                    return await response.text()
            except Exception as e:
                print(f"Error fetching {url}: {str(e)}")
                return None

    # Use a single session for all requests in this batch
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        tasks = [fetch_with_semaphore(session, url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append({
                    "url": urls[i],
                    "error": str(result),
                    "success": False
                })
            elif result is None:
                processed_results.append({
                    "url": urls[i],
                    "error": "Failed to fetch content",
                    "success": False
                })
            else:
                processed_results.append({
                    "url": urls[i],
                    "data": result,
                    "success": True
                })

        return processed_results

# Example usage
async def main():
    """
    Example usage of the async scraping system
    """
    handles = {
        "twitter": "example_user",
        "instagram": "example_user", 
        "tiktok": "example_user"
    }
    
    # Scrape all platforms concurrently
    results = await scrape_all_platforms(handles)
    print("Scraping results:", results)
    
    # Enrich the results
    enriched_results = await run_enrichment_pipeline(results)
    print("Enriched results:", enriched_results)

if __name__ == "__main__":
    # Run the example
    # asyncio.run(main())
    pass