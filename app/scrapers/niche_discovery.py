"""Specialized niche contact discovery scrapers"""
from typing import List, Dict, Optional
import re
import json
from .base_scraper import BaseScraper

class RedditSubmissionScraper(BaseScraper):
    """Reddit/Discord submissions and curator posts"""
    
    def __init__(self):
        super().__init__("reddit_submission_scraper")
    
    async def scrape_submission_posts(self, subreddits: List[str]) -> List[Dict]:
        """Scrape Reddit for submission posts"""
        
        results = []
        submission_keywords = [
            "submissions open", "accepting submissions", "send music",
            "playlist submissions", "demo submissions"
        ]
        
        for subreddit in subreddits:
            try:
                # Use old.reddit.com for easier scraping
                url = f"https://old.reddit.com/r/{subreddit}/search?q=submissions&restrict_sr=1&sort=new"
                html = await self.fetch_page_async(url)
                
                if html:
                    soup = self.parse_html(html)
                    posts = soup.find_all('div', class_='thing')
                    
                    for post in posts[:20]:
                        post_data = self._extract_submission_post(post, subreddit)
                        if post_data:
                            results.append(post_data)
            
            except Exception:
                continue
        
        return results
    
    def _extract_submission_post(self, post_element, subreddit: str) -> Optional[Dict]:
        """Extract submission post data"""
        
        try:
            title_elem = post_element.find('a', class_='title')
            author_elem = post_element.find('a', class_='author')
            
            if not title_elem or not author_elem:
                return None
            
            title = title_elem.get_text()
            author = author_elem.get_text()
            post_url = title_elem.get('href', '')
            
            # Check if it's a submission post
            submission_keywords = ["submission", "send music", "demo", "playlist"]
            if not any(keyword in title.lower() for keyword in submission_keywords):
                return None
            
            return {
                'title': title,
                'author': author,
                'subreddit': subreddit,
                'post_url': post_url,
                'platform': 'reddit',
                'contact_type': 'curator'
            }
        
        except Exception:
            pass
        
        return None

class PodcastGuestScraper(BaseScraper):
    """Podcast guest manager/publicist mentions"""
    
    def __init__(self):
        super().__init__("podcast_guest_scraper")
    
    async def scrape_podcast_credits(self, genre: str = "hip-hop") -> List[Dict]:
        """Scrape podcast episodes for guest credits"""
        
        results = []
        
        # Search for hip-hop podcasts
        search_query = f"{genre} podcast episodes"
        search_url = f"https://duckduckgo.com/html/?q={search_query.replace(' ', '+')}"
        
        try:
            html = await self.fetch_page_async(search_url)
            if not html:
                return results
            
            # Extract podcast episode URLs
            urls = re.findall(r'href="([^"]+)"', html)
            
            for url in urls[:10]:
                if self._is_podcast_url(url):
                    episode_data = await self._scrape_episode_credits(url)
                    if episode_data:
                        results.append(episode_data)
        
        except Exception:
            pass
        
        return results
    
    def _is_podcast_url(self, url: str) -> bool:
        """Check if URL is likely a podcast episode"""
        podcast_indicators = [
            'spotify.com/episode', 'apple.com/podcast', 'soundcloud.com',
            'anchor.fm', 'buzzsprout.com', 'libsyn.com'
        ]
        return any(indicator in url for indicator in podcast_indicators)
    
    async def _scrape_episode_credits(self, url: str) -> Optional[Dict]:
        """Scrape podcast episode for guest credits"""
        
        try:
            html = await self.fetch_page_async(url)
            if not html:
                return None
            
            soup = self.parse_html(html)
            
            # Extract episode description
            desc_selectors = [
                'meta[name="description"]',
                '.episode-description',
                '.show-notes'
            ]
            
            description = ""
            for selector in desc_selectors:
                elem = soup.select_one(selector)
                if elem:
                    description = elem.get('content') or elem.get_text()
                    break
            
            # Look for manager/publicist mentions
            contact_patterns = [
                r'manager[:\s]*([a-zA-Z\s]+)',
                r'publicist[:\s]*([a-zA-Z\s]+)',
                r'contact[:\s]*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'
            ]
            
            contacts = []
            for pattern in contact_patterns:
                matches = re.findall(pattern, description, re.IGNORECASE)
                contacts.extend(matches)
            
            if contacts:
                return {
                    'episode_url': url,
                    'description': description[:300],
                    'contacts': contacts,
                    'platform': 'podcast'
                }
        
        except Exception:
            pass
        
        return None

class VenueBookingScraper(BaseScraper):
    """Venue booking page manager contact scraper"""
    
    def __init__(self):
        super().__init__("venue_booking_scraper")
    
    async def scrape_venue_bookings(self, city: str, genre: str = "hip-hop") -> List[Dict]:
        """Scrape venue booking pages for manager contacts"""
        
        results = []
        
        # Search for venues in city
        search_query = f"{city} {genre} venues booking"
        search_url = f"https://duckduckgo.com/html/?q={search_query.replace(' ', '+')}"
        
        try:
            html = await self.fetch_page_async(search_url)
            if not html:
                return results
            
            # Extract venue URLs
            urls = re.findall(r'href="([^"]+)"', html)
            
            for url in urls[:15]:
                if self._is_venue_url(url):
                    venue_data = await self._scrape_venue_booking_page(url)
                    if venue_data:
                        results.append(venue_data)
        
        except Exception:
            pass
        
        return results
    
    def _is_venue_url(self, url: str) -> bool:
        """Check if URL is likely a venue website"""
        venue_indicators = ['venue', 'club', 'theater', 'hall', 'center']
        return any(indicator in url.lower() for indicator in venue_indicators)
    
    async def _scrape_venue_booking_page(self, url: str) -> Optional[Dict]:
        """Scrape venue booking information"""
        
        try:
            html = await self.fetch_page_async(url)
            if not html:
                return None
            
            soup = self.parse_html(html)
            
            # Look for booking information
            booking_sections = soup.find_all(['div', 'section'], 
                                           text=re.compile(r'booking|contact', re.I))
            
            contacts = []
            for section in booking_sections:
                text = section.get_text()
                emails = self.extract_emails(text)
                contacts.extend(emails)
            
            # Extract venue name
            venue_name = soup.find('title')
            venue_name = venue_name.get_text() if venue_name else url
            
            if contacts:
                return {
                    'venue_name': venue_name,
                    'venue_url': url,
                    'booking_contacts': list(set(contacts)),
                    'platform': 'venue_website'
                }
        
        except Exception:
            pass
        
        return None

class RadioStationScraper(BaseScraper):
    """Radio station playlist manager scraper"""
    
    def __init__(self):
        super().__init__("radio_station_scraper")
    
    async def scrape_radio_contacts(self, genre: str = "hip-hop") -> List[Dict]:
        """Scrape radio station contacts"""
        
        results = []
        
        # Search for radio stations
        search_queries = [
            f"{genre} radio station contacts",
            f"college radio {genre} program director",
            f"local {genre} radio show contacts"
        ]
        
        for query in search_queries:
            try:
                search_url = f"https://duckduckgo.com/html/?q={query.replace(' ', '+')}"
                html = await self.fetch_page_async(search_url)
                
                if html:
                    urls = re.findall(r'href="([^"]+)"', html)
                    
                    for url in urls[:10]:
                        if self._is_radio_url(url):
                            radio_data = await self._scrape_radio_station(url)
                            if radio_data:
                                results.append(radio_data)
            
            except Exception:
                continue
        
        return results
    
    def _is_radio_url(self, url: str) -> bool:
        """Check if URL is likely a radio station"""
        radio_indicators = ['radio', 'fm', 'am', 'wxyz', 'k101', 'wqed']
        return any(indicator in url.lower() for indicator in radio_indicators)
    
    async def _scrape_radio_station(self, url: str) -> Optional[Dict]:
        """Scrape radio station contact info"""
        
        try:
            html = await self.fetch_page_async(url)
            if not html:
                return None
            
            soup = self.parse_html(html)
            
            # Look for program director or music director contacts
            contact_patterns = [
                r'program director[:\s]*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
                r'music director[:\s]*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
                r'submissions[:\s]*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'
            ]
            
            contacts = []
            page_text = soup.get_text()
            
            for pattern in contact_patterns:
                matches = re.findall(pattern, page_text, re.IGNORECASE)
                contacts.extend(matches)
            
            # Extract station name
            station_name = soup.find('title')
            station_name = station_name.get_text() if station_name else url
            
            if contacts:
                return {
                    'station_name': station_name,
                    'station_url': url,
                    'contacts': list(set(contacts)),
                    'platform': 'radio_station'
                }
        
        except Exception:
            pass
        
        return None

class PRFirmScraper(BaseScraper):
    """PR firm client list scraper"""
    
    def __init__(self):
        super().__init__("pr_firm_scraper")
    
    async def scrape_pr_firm_clients(self) -> List[Dict]:
        """Scrape PR firm case studies and client lists"""
        
        results = []
        
        # Search for music PR firms
        search_query = "music PR firm clients case studies"
        search_url = f"https://duckduckgo.com/html/?q={search_query.replace(' ', '+')}"
        
        try:
            html = await self.fetch_page_async(search_url)
            if not html:
                return results
            
            urls = re.findall(r'href="([^"]+)"', html)
            
            for url in urls[:20]:
                if self._is_pr_firm_url(url):
                    firm_data = await self._scrape_pr_firm(url)
                    if firm_data:
                        results.append(firm_data)
        
        except Exception:
            pass
        
        return results
    
    def _is_pr_firm_url(self, url: str) -> bool:
        """Check if URL is likely a PR firm"""
        pr_indicators = ['pr', 'publicist', 'communications', 'media', 'press']
        return any(indicator in url.lower() for indicator in pr_indicators)
    
    async def _scrape_pr_firm(self, url: str) -> Optional[Dict]:
        """Scrape PR firm for client information"""
        
        try:
            html = await self.fetch_page_async(url)
            if not html:
                return None
            
            soup = self.parse_html(html)
            
            # Look for client sections
            client_sections = soup.find_all(['div', 'section'], 
                                          text=re.compile(r'client|case study|portfolio', re.I))
            
            clients = []
            contacts = []
            
            for section in client_sections:
                text = section.get_text()
                
                # Extract client names (artists/labels)
                # This is simplified - would need more sophisticated NLP
                potential_clients = re.findall(r'([A-Z][a-z]+ [A-Z][a-z]+)', text)
                clients.extend(potential_clients)
                
                # Extract contact emails
                emails = self.extract_emails(text)
                contacts.extend(emails)
            
            # Extract firm name
            firm_name = soup.find('title')
            firm_name = firm_name.get_text() if firm_name else url
            
            if clients or contacts:
                return {
                    'firm_name': firm_name,
                    'firm_url': url,
                    'clients': list(set(clients)),
                    'contacts': list(set(contacts)),
                    'platform': 'pr_firm'
                }
        
        except Exception:
            pass
        
        return None

class NicheDiscoveryScraper(BaseScraper):
    """Meta-scraper for all niche discovery strategies"""
    
    def __init__(self):
        super().__init__("niche_discovery_scraper")
        self.scrapers = {
            'reddit': RedditSubmissionScraper(),
            'podcasts': PodcastGuestScraper(),
            'venues': VenueBookingScraper(),
            'radio': RadioStationScraper(),
            'pr_firms': PRFirmScraper()
        }
    
    async def comprehensive_niche_discovery(self, genre: str = "hip-hop", city: str = "New York") -> Dict[str, List[Dict]]:
        """Run comprehensive niche contact discovery"""
        
        results = {}
        
        # Reddit submissions
        try:
            subreddits = ['hiphopheads', 'makinghiphop', 'trapproduction', 'WeAreTheMusicMakers']
            reddit_results = await self.scrapers['reddit'].scrape_submission_posts(subreddits)
            results['reddit_submissions'] = reddit_results
        except Exception:
            results['reddit_submissions'] = []
        
        # Podcast contacts
        try:
            podcast_results = await self.scrapers['podcasts'].scrape_podcast_credits(genre)
            results['podcast_contacts'] = podcast_results
        except Exception:
            results['podcast_contacts'] = []
        
        # Venue bookings
        try:
            venue_results = await self.scrapers['venues'].scrape_venue_bookings(city, genre)
            results['venue_contacts'] = venue_results
        except Exception:
            results['venue_contacts'] = []
        
        # Radio stations
        try:
            radio_results = await self.scrapers['radio'].scrape_radio_contacts(genre)
            results['radio_contacts'] = radio_results
        except Exception:
            results['radio_contacts'] = []
        
        # PR firms
        try:
            pr_results = await self.scrapers['pr_firms'].scrape_pr_firm_clients()
            results['pr_firm_contacts'] = pr_results
        except Exception:
            results['pr_firm_contacts'] = []
        
        return results
