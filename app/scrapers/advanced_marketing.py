"""Advanced marketing contact discovery strategies"""
from typing import List, Dict, Optional
import re
import json
from urllib.parse import urljoin
from .base_scraper import BaseScraper

class MusicBrainzScraper(BaseScraper):
    """MusicBrainz/Discogs API for manager credits"""
    
    def __init__(self):
        super().__init__("musicbrainz_scraper")
        self.mb_base = "https://musicbrainz.org/ws/2"
        self.discogs_base = "https://api.discogs.com"
    
    async def scrape_manager_credits(self, artist_name: str) -> List[Dict]:
        """Find manager credits from release data"""
        
        results = []
        
        # Search MusicBrainz for artist
        search_url = f"{self.mb_base}/artist/?query={artist_name}&fmt=json"
        response = await self.fetch_page_async(search_url)
        if not response:
            return results
        
        try:
            data = json.loads(response)
            artists = data.get('artists', [])
            
            for artist in artists[:3]:  # Top 3 matches
                artist_id = artist['id']
                
                # Get releases for artist
                releases_url = f"{self.mb_base}/release/?artist={artist_id}&inc=artist-rels&fmt=json"
                releases_response = await self.fetch_page_async(releases_url)
                
                if releases_response:
                    releases_data = json.loads(releases_response)
                    
                    for release in releases_data.get('releases', [])[:10]:
                        # Look for manager relationships
                        for relation in release.get('artist-credit', [{}])[0].get('artist', {}).get('relations', []):
                            if relation.get('type') in ['manager', 'booking agent']:
                                manager_data = {
                                    'name': relation.get('artist', {}).get('name'),
                                    'type': relation.get('type'),
                                    'artist': artist_name,
                                    'release': release.get('title'),
                                    'source': 'musicbrainz'
                                }
                                results.append(manager_data)
        
        except Exception as e:
            self.errors.append({"source": "musicbrainz", "error": str(e)})
        
        return results

class LinkedInScraper(BaseScraper):
    """LinkedIn targeted search for music industry contacts"""
    
    def __init__(self):
        super().__init__("linkedin_scraper")
    
    async def scrape_music_industry_contacts(self, titles: List[str], genre: str = "hip-hop") -> List[Dict]:
        """Search LinkedIn for music industry professionals"""
        
        results = []
        
        for title in titles:
            try:
                # Construct search query
                query = f"{title} {genre} music"
                search_url = f"https://www.linkedin.com/search/results/people/?keywords={query.replace(' ', '%20')}"
                
                html = await self.fetch_page_async(search_url)
                if not html:
                    continue
                
                soup = self.parse_html(html)
                profiles = soup.find_all('div', class_='entity-result__item')
                
                for profile in profiles[:10]:
                    profile_data = self._extract_linkedin_profile(profile, title)
                    if profile_data:
                        results.append(profile_data)
            
            except Exception as e:
                self.errors.append({"title": title, "error": str(e)})
        
        return results
    
    def _extract_linkedin_profile(self, profile_element, title: str) -> Optional[Dict]:
        """Extract LinkedIn profile data"""
        
        try:
            name_elem = profile_element.find('span', {'aria-hidden': 'true'})
            title_elem = profile_element.find('div', class_='entity-result__primary-subtitle')
            
            if name_elem and title_elem:
                name = name_elem.get_text().strip()
                job_title = title_elem.get_text().strip()
                
                # Infer email domain from company
                company_match = re.search(r'at (.+?)(?:\s|$)', job_title)
                domain = None
                if company_match:
                    company = company_match.group(1).strip()
                    domain = self._infer_email_domain(company)
                
                return {
                    'name': name,
                    'title': job_title,
                    'search_title': title,
                    'inferred_domain': domain,
                    'platform': 'linkedin',
                    'contact_type': self._map_title_to_type(title)
                }
        
        except Exception:
            pass
        
        return None
    
    def _infer_email_domain(self, company: str) -> Optional[str]:
        """Infer email domain from company name"""
        # Simple domain inference logic
        company_clean = re.sub(r'[^a-zA-Z0-9\s]', '', company).lower()
        words = company_clean.split()
        
        if len(words) == 1:
            return f"{words[0]}.com"
        elif len(words) == 2:
            return f"{words[0]}{words[1]}.com"
        
        return None
    
    def _map_title_to_type(self, title: str) -> str:
        """Map job title to contact type"""
        title_lower = title.lower()
        
        if 'a&r' in title_lower or 'ar' in title_lower:
            return 'ar_rep'
        elif 'manager' in title_lower:
            return 'manager'
        elif 'publicist' in title_lower or 'pr' in title_lower:
            return 'publicist'
        else:
            return 'industry_contact'

class YouTubeScraper(BaseScraper):
    """YouTube About page email extraction"""
    
    def __init__(self):
        super().__init__("youtube_about_scraper")
    
    async def scrape_channel_emails(self, search_query: str, max_channels: int = 50) -> List[Dict]:
        """Extract business emails from YouTube About pages"""
        
        results = []
        
        # Search for channels
        search_url = f"https://www.youtube.com/results?search_query={search_query.replace(' ', '+')}&sp=EgIQAg%253D%253D"  # Channel filter
        
        html = await self.fetch_page_async(search_url)
        if not html:
            return results
        
        # Extract channel URLs from search results
        channel_urls = re.findall(r'/channel/([a-zA-Z0-9_-]+)', html)
        
        for channel_id in channel_urls[:max_channels]:
            try:
                about_url = f"https://www.youtube.com/channel/{channel_id}/about"
                about_html = await self.fetch_page_async(about_url)
                
                if about_html:
                    channel_data = self._extract_channel_data(about_html, channel_id)
                    if channel_data:
                        results.append(channel_data)
            
            except Exception as e:
                continue
        
        return results
    
    def _extract_channel_data(self, html: str, channel_id: str) -> Optional[Dict]:
        """Extract channel data from About page"""
        
        try:
            soup = self.parse_html(html)
            
            # Extract channel name
            name_elem = soup.find('meta', {'property': 'og:title'})
            channel_name = name_elem['content'] if name_elem else f"Channel_{channel_id}"
            
            # Extract description
            desc_elem = soup.find('meta', {'name': 'description'})
            description = desc_elem['content'] if desc_elem else ""
            
            # Extract emails from description
            emails = self.extract_emails(description)
            
            # Look for business email patterns in HTML
            business_patterns = [
                r'business[:\s]*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
                r'contact[:\s]*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
                r'booking[:\s]*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'
            ]
            
            for pattern in business_patterns:
                matches = re.findall(pattern, html, re.IGNORECASE)
                emails.extend(matches)
            
            if emails:
                return {
                    'channel_name': channel_name,
                    'channel_id': channel_id,
                    'description': description,
                    'emails': list(set(emails)),
                    'platform': 'youtube',
                    'source_url': f"https://youtube.com/channel/{channel_id}"
                }
        
        except Exception:
            pass
        
        return None

class TeamPageScraper(BaseScraper):
    """Artist/label team page scraper"""
    
    def __init__(self):
        super().__init__("team_page_scraper")
    
    async def scrape_artist_team_pages(self, artist_name: str) -> List[Dict]:
        """Scrape artist official sites for team pages"""
        
        results = []
        
        # Search for artist official site
        search_queries = [
            f"{artist_name} official site",
            f"{artist_name} band website",
            f"{artist_name} music team"
        ]
        
        for query in search_queries:
            try:
                # Use search engine to find official sites
                search_url = f"https://duckduckgo.com/html/?q={query.replace(' ', '+')}"
                search_html = await self.fetch_page_async(search_url)
                
                if search_html:
                    # Extract website URLs from search results
                    urls = re.findall(r'href="([^"]+)"', search_html)
                    
                    for url in urls[:5]:  # Check top 5 results
                        if self._is_likely_official_site(url, artist_name):
                            team_data = await self._scrape_team_page(url)
                            if team_data:
                                results.extend(team_data)
            
            except Exception:
                continue
        
        return results
    
    def _is_likely_official_site(self, url: str, artist_name: str) -> bool:
        """Check if URL is likely an official artist site"""
        
        # Skip search engines, social media, streaming platforms
        skip_domains = [
            'google.com', 'youtube.com', 'spotify.com', 'apple.com',
            'instagram.com', 'twitter.com', 'facebook.com', 'soundcloud.com'
        ]
        
        for domain in skip_domains:
            if domain in url:
                return False
        
        # Check if artist name is in domain
        artist_clean = re.sub(r'[^a-zA-Z0-9]', '', artist_name.lower())
        return artist_clean in url.lower()
    
    async def _scrape_team_page(self, base_url: str) -> List[Dict]:
        """Scrape team page from artist website"""
        
        results = []
        
        # Common team page paths
        team_paths = ['/team', '/about', '/contact', '/management', '/press']
        
        for path in team_paths:
            try:
                team_url = urljoin(base_url, path)
                html = await self.fetch_page_async(team_url)
                
                if html:
                    team_contacts = self._extract_team_contacts(html, team_url)
                    results.extend(team_contacts)
            
            except Exception:
                continue
        
        return results
    
    def _extract_team_contacts(self, html: str, url: str) -> List[Dict]:
        """Extract team contacts from page"""
        
        contacts = []
        soup = self.parse_html(html)
        
        # Look for team member sections
        team_sections = soup.find_all(['div', 'section'], 
                                    class_=re.compile(r'team|staff|contact|management', re.I))
        
        for section in team_sections:
            text = section.get_text()
            emails = self.extract_emails(text)
            
            # Look for role indicators
            roles = ['manager', 'publicist', 'booking', 'press', 'a&r']
            
            for email in emails:
                # Try to find associated role
                role = 'team_member'
                for r in roles:
                    if r in text.lower():
                        role = r
                        break
                
                contacts.append({
                    'email': email,
                    'role': role,
                    'source_url': url,
                    'context': text[:200]  # First 200 chars for context
                })
        
        return contacts

class PressKitScraper(BaseScraper):
    """Press kit PDF contact extractor"""
    
    def __init__(self):
        super().__init__("press_kit_scraper")
    
    async def scrape_press_kit_contacts(self, artist_name: str) -> List[Dict]:
        """Search and parse press kit PDFs for contacts"""
        
        results = []
        
        # Search for press kits
        search_query = f"{artist_name} press kit PDF filetype:pdf"
        search_url = f"https://duckduckgo.com/html/?q={search_query.replace(' ', '+')}"
        
        try:
            search_html = await self.fetch_page_async(search_url)
            if not search_html:
                return results
            
            # Extract PDF URLs
            pdf_urls = re.findall(r'href="([^"]+\.pdf[^"]*)"', search_html)
            
            for pdf_url in pdf_urls[:5]:  # Limit to 5 PDFs
                try:
                    contacts = await self._extract_pdf_contacts(pdf_url, artist_name)
                    results.extend(contacts)
                except Exception:
                    continue
        
        except Exception as e:
            self.errors.append({"source": "press_kit_search", "error": str(e)})
        
        return results
    
    async def _extract_pdf_contacts(self, pdf_url: str, artist_name: str) -> List[Dict]:
        """Extract contacts from PDF (simplified - would use pdfminer in production)"""
        
        # Note: This is a simplified version. In production, you'd use:
        # from pdfminer.high_level import extract_text
        # text = extract_text(pdf_url)
        
        contacts = []
        
        try:
            # For now, just try to fetch as text (some PDFs are text-based)
            response = await self.fetch_page_async(pdf_url)
            if response:
                # Extract emails from PDF content
                emails = self.extract_emails(response)
                
                for email in emails:
                    contacts.append({
                        'email': email,
                        'artist': artist_name,
                        'source': 'press_kit_pdf',
                        'source_url': pdf_url
                    })
        
        except Exception:
            pass
        
        return contacts

class AdvancedMarketingScraper(BaseScraper):
    """Meta-scraper combining all advanced marketing strategies"""
    
    def __init__(self):
        super().__init__("advanced_marketing_scraper")
        self.scrapers = {
            'musicbrainz': MusicBrainzScraper(),
            'linkedin': LinkedInScraper(),
            'youtube': YouTubeScraper(),
            'team_pages': TeamPageScraper(),
            'press_kits': PressKitScraper()
        }
    
    async def comprehensive_contact_discovery(self, artist_name: str, genre: str = "hip-hop") -> Dict[str, List[Dict]]:
        """Run comprehensive contact discovery across all strategies"""
        
        results = {}
        
        # MusicBrainz manager credits
        try:
            mb_results = await self.scrapers['musicbrainz'].scrape_manager_credits(artist_name)
            results['manager_credits'] = mb_results
        except Exception:
            results['manager_credits'] = []
        
        # LinkedIn industry contacts
        try:
            titles = ['A&R', 'Manager', 'Publicist', 'Music Supervisor', 'Booking Agent']
            linkedin_results = await self.scrapers['linkedin'].scrape_music_industry_contacts(titles, genre)
            results['linkedin_contacts'] = linkedin_results
        except Exception:
            results['linkedin_contacts'] = []
        
        # YouTube channel contacts
        try:
            youtube_query = f"{genre} playlist curator"
            youtube_results = await self.scrapers['youtube'].scrape_channel_emails(youtube_query)
            results['youtube_contacts'] = youtube_results
        except Exception:
            results['youtube_contacts'] = []
        
        # Artist team pages
        try:
            team_results = await self.scrapers['team_pages'].scrape_artist_team_pages(artist_name)
            results['team_contacts'] = team_results
        except Exception:
            results['team_contacts'] = []
        
        # Press kit contacts
        try:
            press_results = await self.scrapers['press_kits'].scrape_press_kit_contacts(artist_name)
            results['press_kit_contacts'] = press_results
        except Exception:
            results['press_kit_contacts'] = []
        
        return results
