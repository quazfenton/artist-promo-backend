"""OSS alternative platform scrapers (Nitter, Proxigram, ProxiTok, etc.)"""
from typing import List, Dict, Optional
import re
from .base_scraper import BaseScraper

class NitterScraper(BaseScraper):
    """Twitter/X scraper using Nitter instances"""
    
    def __init__(self):
        super().__init__("nitter_scraper")
        self.instances = [
            "nitter.net", "nitter.it", "nitter.unixfox.eu",
            "nitter.domain.glass", "nitter.eu"
        ]
    
    async def scrape_bio_emails(self, query: str, max_results: int = 50) -> List[Dict]:
        """Search Twitter bios for contact emails"""
        
        results = []
        search_terms = [
            f"{query} bookings", f"{query} press", f"{query} manager",
            f"{query} contact", f"{query} email"
        ]
        
        for term in search_terms:
            for instance in self.instances:
                try:
                    url = f"https://{instance}/search?f=users&q={term.replace(' ', '%20')}"
                    html = await self.fetch_page_async(url)
                    if not html:
                        continue
                    
                    soup = self.parse_html(html)
                    profiles = soup.find_all('div', class_='timeline-item')
                    
                    for profile in profiles[:max_results//len(search_terms)]:
                        profile_data = self._extract_profile_data(profile, instance)
                        if profile_data and profile_data.get('emails'):
                            results.append(profile_data)
                    
                    break  # Success with this instance
                except Exception as e:
                    continue  # Try next instance
        
        return results
    
    def _extract_profile_data(self, profile_element, instance: str) -> Optional[Dict]:
        """Extract profile data from Nitter profile"""
        
        try:
            username_elem = profile_element.find('a', class_='username')
            bio_elem = profile_element.find('div', class_='tweet-content')
            
            if not username_elem or not bio_elem:
                return None
            
            username = username_elem.text.strip('@')
            bio_text = bio_elem.get_text()
            
            # Extract emails from bio
            emails = self.extract_emails(bio_text)
            
            # Look for booking/press keywords
            contact_keywords = ['booking', 'press', 'manager', 'contact', 'business']
            has_contact_keywords = any(keyword in bio_text.lower() for keyword in contact_keywords)
            
            if emails and has_contact_keywords:
                return {
                    'username': username,
                    'bio': bio_text,
                    'emails': emails,
                    'platform': 'twitter',
                    'source_url': f"https://{instance}/{username}",
                    'contact_type': self._infer_contact_type(bio_text)
                }
        
        except Exception:
            pass
        
        return None
    
    def _infer_contact_type(self, bio: str) -> str:
        """Infer contact type from bio text"""
        bio_lower = bio.lower()
        
        if any(term in bio_lower for term in ['a&r', 'ar rep', 'label']):
            return 'ar_rep'
        elif any(term in bio_lower for term in ['manager', 'mgmt']):
            return 'manager'
        elif any(term in bio_lower for term in ['press', 'pr', 'publicist']):
            return 'publicist'
        elif any(term in bio_lower for term in ['booking', 'book']):
            return 'venue_booker'
        else:
            return 'influencer'

class ProxigramScraper(BaseScraper):
    """Instagram scraper using Proxigram instances"""
    
    def __init__(self):
        super().__init__("proxigram_scraper")
        self.instances = [
            "proxigram.lunar.icu", "proxigram.privacy.com.de"
        ]
    
    async def scrape_business_contacts(self, hashtag: str, max_profiles: int = 100) -> List[Dict]:
        """Scrape Instagram business profiles via Proxigram"""
        
        results = []
        
        for instance in self.instances:
            try:
                url = f"https://{instance}/tags/{hashtag.lstrip('#')}"
                html = await self.fetch_page_async(url)
                if not html:
                    continue
                
                soup = self.parse_html(html)
                posts = soup.find_all('div', class_='post')
                
                for post in posts[:max_profiles]:
                    profile_link = post.find('a', href=re.compile(r'^/[^/]+$'))
                    if profile_link:
                        username = profile_link['href'].strip('/')
                        profile_data = await self._scrape_profile(instance, username)
                        if profile_data:
                            results.append(profile_data)
                
                break  # Success with this instance
            except Exception:
                continue
        
        return results
    
    async def _scrape_profile(self, instance: str, username: str) -> Optional[Dict]:
        """Scrape individual Instagram profile"""
        
        try:
            url = f"https://{instance}/{username}"
            html = await self.fetch_page_async(url)
            if not html:
                return None
            
            soup = self.parse_html(html)
            
            # Extract bio
            bio_elem = soup.find('div', class_='biography')
            bio = bio_elem.get_text() if bio_elem else ""
            
            # Extract contact button/email
            contact_elem = soup.find('a', href=re.compile(r'mailto:'))
            emails = []
            if contact_elem:
                email = contact_elem['href'].replace('mailto:', '')
                emails.append(email)
            
            # Extract from bio text
            bio_emails = self.extract_emails(bio)
            emails.extend(bio_emails)
            
            # Check if business account
            is_business = 'contact' in bio.lower() or 'business' in bio.lower()
            
            if emails and is_business:
                return {
                    'username': username,
                    'bio': bio,
                    'emails': list(set(emails)),
                    'platform': 'instagram',
                    'source_url': f"https://instagram.com/{username}",
                    'is_business': True
                }
        
        except Exception:
            pass
        
        return None

class ProxiTokScraper(BaseScraper):
    """TikTok scraper using ProxiTok instances"""
    
    def __init__(self):
        super().__init__("proxitok_scraper")
        self.instances = [
            "proxitok.pabloferreiro.es", "tok.habedieeh.re"
        ]
    
    async def scrape_creator_contacts(self, hashtag: str, max_creators: int = 50) -> List[Dict]:
        """Scrape TikTok creator contacts via ProxiTok"""
        
        results = []
        
        for instance in self.instances:
            try:
                url = f"https://{instance}/tag/{hashtag.lstrip('#')}"
                html = await self.fetch_page_async(url)
                if not html:
                    continue
                
                soup = self.parse_html(html)
                videos = soup.find_all('div', class_='video-feed-item')
                
                creators_seen = set()
                
                for video in videos:
                    creator_link = video.find('a', class_='creator')
                    if creator_link and len(creators_seen) < max_creators:
                        username = creator_link.get('href', '').strip('/@')
                        if username and username not in creators_seen:
                            creators_seen.add(username)
                            profile_data = await self._scrape_creator_profile(instance, username)
                            if profile_data:
                                results.append(profile_data)
                
                break
            except Exception:
                continue
        
        return results
    
    async def _scrape_creator_profile(self, instance: str, username: str) -> Optional[Dict]:
        """Scrape TikTok creator profile"""
        
        try:
            url = f"https://{instance}/@{username}"
            html = await self.fetch_page_async(url)
            if not html:
                return None
            
            soup = self.parse_html(html)
            
            # Extract bio
            bio_elem = soup.find('div', class_='bio')
            bio = bio_elem.get_text() if bio_elem else ""
            
            # Extract emails from bio
            emails = self.extract_emails(bio)
            
            # Look for business indicators
            business_keywords = ['booking', 'business', 'contact', 'collab', 'brand']
            is_business = any(keyword in bio.lower() for keyword in business_keywords)
            
            if emails and is_business:
                return {
                    'username': username,
                    'bio': bio,
                    'emails': emails,
                    'platform': 'tiktok',
                    'source_url': f"https://tiktok.com/@{username}",
                    'is_business': is_business
                }
        
        except Exception:
            pass
        
        return None

class LibreRedirectScraper(BaseScraper):
    """Meta-scraper using LibreRedirect alternatives"""
    
    def __init__(self):
        super().__init__("libre_redirect_scraper")
        self.platform_scrapers = {
            'twitter': NitterScraper(),
            'instagram': ProxigramScraper(),
            'tiktok': ProxiTokScraper()
        }
    
    async def scrape_all_platforms(self, query: str, max_per_platform: int = 25) -> Dict[str, List[Dict]]:
        """Scrape contacts across all OSS alternative platforms"""
        
        results = {}
        
        # Twitter via Nitter
        try:
            twitter_results = await self.platform_scrapers['twitter'].scrape_bio_emails(
                query, max_per_platform
            )
            results['twitter'] = twitter_results
        except Exception as e:
            results['twitter'] = []
        
        # Instagram via Proxigram
        try:
            instagram_results = await self.platform_scrapers['instagram'].scrape_business_contacts(
                query, max_per_platform
            )
            results['instagram'] = instagram_results
        except Exception as e:
            results['instagram'] = []
        
        # TikTok via ProxiTok
        try:
            tiktok_results = await self.platform_scrapers['tiktok'].scrape_creator_contacts(
                query, max_per_platform
            )
            results['tiktok'] = tiktok_results
        except Exception as e:
            results['tiktok'] = []
        
        return results
