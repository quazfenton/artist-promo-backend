"""
Link-in-bio recursive resolver
"""
import asyncio
import aiohttp
from bs4 import BeautifulSoup
from typing import Dict, List, Optional
from urllib.parse import urljoin, urlparse
import re

# Common link-in-bio platforms
LINK_IN_BIO_DOMAINS = {
    'linktr.ee', 'linktree.com', 'beacons.ai', 'campsite.bio',
    'bio.fm', 'linkin.bio', 'many.link', 'uncut.page',
    'tap.bio', 'linklyhq.com', 'lnk.bio', 'smash.page'
}

EMAIL_REGEX = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'

def is_link_in_bio_url(url: str) -> bool:
    """
    Check if a URL is a link-in-bio platform
    """
    domain = urlparse(url).netloc.lower()
    return any(link_domain in domain for link_domain in LINK_IN_BIO_DOMAINS)

def extract_emails_from_text(text: str) -> List[str]:
    """
    Extract emails from text using regex
    """
    return list(set(re.findall(EMAIL_REGEX, text or "")))

async def resolve_link_tree(url: str, depth: int = 1, session: Optional[aiohttp.ClientSession] = None, visited_urls: set = None) -> Dict:
    """
    Recursively resolve link trees from link-in-bio pages
    """
    if visited_urls is None:
        visited_urls = set()

    if depth == 0 or url in visited_urls:
        return {"emails": [], "links": [], "children": []}

    # Add current URL to visited set
    visited_urls.add(url)
    
    # Create session if not provided
    created_session = False
    if session is None:
        session = aiohttp.ClientSession()
        created_session = True
    
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
            if response.status != 200:
                return {"emails": [], "links": [], "children": []}

            html = await response.text()
            soup = BeautifulSoup(html, "html.parser")

            # Extract emails from the page
            page_text = soup.get_text()
            emails = extract_emails_from_text(page_text)

            # Extract links
            links = []
            for a_tag in soup.find_all('a', href=True):
                href = a_tag['href']
                if href.startswith(('http://', 'https://')):
                    full_url = urljoin(url, href)
                    links.append(full_url)

            # Recursively resolve child links if they're also link-in-bio
            children = []
            for link in links:
                if is_link_in_bio_url(link):
                    child_result = await resolve_link_tree(link, depth - 1, session, visited_urls.copy())
                    children.append(child_result)

            result = {
                "url": url,
                "emails": emails,
                "links": links,
                "children": children,
                "title": soup.title.string if soup.title else "",
                "description": "",
            }

            # Try to get meta description
            desc_tag = soup.find('meta', attrs={'name': 'description'})
            if desc_tag:
                result["description"] = desc_tag.get('content', '')

            return result

    except Exception as e:
        print(f"Error resolving link tree for {url}: {str(e)}")
        return {"emails": [], "links": [], "children": []}
    finally:
        if created_session:
            await session.close()

async def resolve_multiple_link_trees(urls: List[str], max_depth: int = 2) -> List[Dict]:
    """
    Resolve multiple link trees concurrently
    """
    async with aiohttp.ClientSession() as session:
        # Each URL gets its own visited_urls set to avoid cross-contamination
        tasks = [resolve_link_tree(url, max_depth, session) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out any exceptions
        valid_results = []
        for result in results:
            if not isinstance(result, Exception):
                valid_results.append(result)
            else:
                print(f"Error in link tree resolution: {result}")

        return valid_results

def extract_contact_info_from_bio(bio_html: str) -> Dict[str, any]:
    """
    Extract contact information from bio text/html
    """
    soup = BeautifulSoup(bio_html, "html.parser")
    text = soup.get_text()
    
    emails = extract_emails_from_text(text)
    
    # Look for common contact phrases
    contact_patterns = {
        "booking": r"(?:booking|bookings|book me|contact for booking)\s*[:@]?\s*([^\s<>\n]+@[^\s<>\n]+)",
        "press": r"(?:press|media contact)\s*[:@]?\s*([^\s<>\n]+@[^\s<>\n]+)",
        "management": r"(?:management|mgmt|manager)\s*[:@]?\s*([^\s<>\n]+@[^\s<>\n]+)",
        "general": r"(?:contact|reach out|email)\s*[:@]?\s*([^\s<>\n]+@[^\s<>\n]+)"
    }
    
    contact_info = {"emails": emails, "by_type": {}}
    
    for contact_type, pattern in contact_patterns.items():
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            contact_info["by_type"][contact_type] = matches
    
    return contact_info

def find_social_links_in_bio(bio_html: str) -> List[str]:
    """
    Find social media links in bio text
    """
    soup = BeautifulSoup(bio_html, "html.parser")
    text = soup.get_text()
    
    # Common social media patterns
    social_patterns = [
        r'(?:https?://)?(?:www\.)?instagram\.com/([a-zA-Z0-9_.]+)/?',
        r'(?:https?://)?(?:www\.)?twitter\.com/([a-zA-Z0-9_]+)/?',
        r'(?:https?://)?(?:www\.)?facebook\.com/([a-zA-Z0-9_.]+)/?',
        r'(?:https?://)?(?:www\.)?tiktok\.com/@([a-zA-Z0-9_.]+)/?',
        r'(?:https?://)?(?:www\.)?youtube\.com/(?:@|c/)?([a-zA-Z0-9_]+)/?',
    ]
    
    links = []
    for pattern in social_patterns:
        matches = re.findall(pattern, text)
        for match in matches:
            if 'instagram' in pattern:
                links.append(f"https://instagram.com/{match}")
            elif 'twitter' in pattern:
                links.append(f"https://twitter.com/{match}")
            elif 'facebook' in pattern:
                links.append(f"https://facebook.com/{match}")
            elif 'tiktok' in pattern:
                links.append(f"https://tiktok.com/@{match}")
            elif 'youtube' in pattern:
                links.append(f"https://youtube.com/@{match}")
    
    return list(set(links))  # Remove duplicates

def aggregate_contact_info_from_multiple_sources(sources: List[Dict]) -> Dict:
    """
    Aggregate contact info from multiple sources (bio, link-tree, etc.)
    """
    all_emails = set()
    all_links = set()
    by_source = {}
    
    for source in sources:
        source_name = source.get('source', 'unknown')
        by_source[source_name] = {
            'emails': source.get('emails', []),
            'links': source.get('links', []),
            'description': source.get('description', '')
        }
        
        all_emails.update(source.get('emails', []))
        all_links.update(source.get('links', []))
    
    return {
        "consolidated_emails": list(all_emails),
        "consolidated_links": list(all_links),
        "by_source": by_source,
        "total_sources": len(sources)
    }

# Example usage function
async def process_artist_bio_pages(artist_handles: Dict[str, str]) -> Dict:
    """
    Process multiple artist bio pages and link trees
    """
    results = {}
    
    # Process each platform's bio page
    for platform, handle in artist_handles.items():
        if platform == "linktree":
            url = f"https://linktr.ee/{handle}"
        elif platform == "linktree_custom":
            url = handle  # Full URL provided
        elif platform == "bio":
            url = f"https://bio.fm/{handle}"
        else:
            continue  # Skip unsupported platforms
        
        if is_link_in_bio_url(url):
            async with aiohttp.ClientSession() as session:
                result = await resolve_link_tree(url, depth=2, session=session, visited_urls=set())
            results[platform] = result
    
    return results