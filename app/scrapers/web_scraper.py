"""
Enhanced web contact scraper with advanced extraction
"""
from typing import List, Dict, Optional
from loguru import logger
import asyncio
from urllib.parse import urljoin, urlparse
import re
from .base_scraper import BaseScraper


class WebContactScraper(BaseScraper):
    """Enhanced web scraper for contact information"""
    
    def __init__(self):
        super().__init__("web_contact_scraper")
        
        # Common contact page patterns
        self.contact_patterns = [
            '/contact', '/contact-us', '/about', '/team', 
            '/press', '/media', '/booking', '/management',
            '/info', '/reach-out', '/get-in-touch'
        ]
        
        # Email extraction patterns
        self.email_selectors = [
            'a[href^="mailto:"]',
            '.email', '.contact-email', '.business-email',
            '[data-email]', '[data-contact]'
        ]
    
    async def scrape(self, url: str) -> Optional[Dict]:
        """Enhanced web scraping with multiple strategies"""
        
        logger.info(f"[{self.name}] Starting enhanced scrape of {url}")
        
        async with self:
            try:
                # Main page scrape
                main_result = await self._scrape_page(url)
                
                # Find and scrape contact pages
                contact_pages = await self._find_contact_pages(url)
                
                # Scrape social media pages
                social_results = await self._scrape_social_links(url)
                
                # Combine all results
                combined_result = self._combine_results(main_result, contact_pages, social_results)
                combined_result['source_url'] = url
                
                if combined_result['emails'] or combined_result['social_handles']:
                    self.save_result(combined_result)
                    return combined_result
                
                return None
                
            except Exception as e:
                logger.error(f"[{self.name}] Enhanced scrape failed for {url}: {str(e)}")
                return None
    
    async def _scrape_page(self, url: str) -> Dict:
        """Scrape a single page for contact information"""
        
        try:
            html_content = await self.fetch_page_async(url)
            if not html_content:
                return {"emails": [], "social_handles": {}, "contact_info": {}}
            
            soup = self.parse_html(html_content)
            
            # Extract emails
            emails = self._extract_emails_enhanced(soup, html_content)
            
            # Extract social handles
            social_handles = self.extract_social_handles(html_content, soup)
            
            # Extract additional contact info
            contact_info = self._extract_contact_info(soup)
            
            # Extract business information
            business_info = self._extract_business_info(soup)
            
            return {
                "emails": emails,
                "social_handles": social_handles,
                "contact_info": contact_info,
                "business_info": business_info
            }
            
        except Exception as e:
            logger.error(f"[{self.name}] Error scraping page {url}: {str(e)}")
            return {"emails": [], "social_handles": {}, "contact_info": {}}
    
    async def _find_contact_pages(self, base_url: str) -> List[Dict]:
        """Find and scrape potential contact pages"""
        
        contact_results = []
        
        # Try common contact page URLs
        for pattern in self.contact_patterns:
            contact_url = urljoin(base_url, pattern)
            
            try:
                result = await self._scrape_page(contact_url)
                if result['emails'] or result['contact_info']:
                    result['page_type'] = 'contact_page'
                    result['url'] = contact_url
                    contact_results.append(result)
                
                # Rate limiting
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.debug(f"[{self.name}] Contact page not found: {contact_url}")
                continue
        
        return contact_results
    
    async def _scrape_social_links(self, base_url: str) -> Dict:
        """Extract and analyze social media links"""
        
        try:
            html_content = await self.fetch_page_async(base_url)
            if not html_content:
                return {}
            
            soup = self.parse_html(html_content)
            
            # Find social media links
            social_links = {}
            
            # Instagram
            instagram_links = soup.find_all('a', href=re.compile(r'instagram\.com/'))
            if instagram_links:
                instagram_url = instagram_links[0]['href']
                username = instagram_url.split('/')[-1].split('?')[0]
                social_links['instagram'] = {
                    'username': username,
                    'url': instagram_url
                }
            
            # Twitter
            twitter_links = soup.find_all('a', href=re.compile(r'twitter\.com/'))
            if twitter_links:
                twitter_url = twitter_links[0]['href']
                username = twitter_url.split('/')[-1].split('?')[0]
                social_links['twitter'] = {
                    'username': username,
                    'url': twitter_url
                }
            
            return social_links
            
        except Exception as e:
            logger.error(f"[{self.name}] Error extracting social links: {str(e)}")
            return {}
    
    def _extract_emails_enhanced(self, soup, html_content: str) -> List[str]:
        """Enhanced email extraction with multiple methods"""
        
        emails = set()
        
        # Method 1: CSS selectors
        for selector in self.email_selectors:
            elements = soup.select(selector)
            for element in elements:
                if element.get('href') and element['href'].startswith('mailto:'):
                    email = element['href'].replace('mailto:', '').split('?')[0]
                    emails.add(email)
                elif element.get('data-email'):
                    emails.add(element['data-email'])
                elif element.text:
                    found_emails = self.extract_emails(element.text)
                    emails.update(found_emails)
        
        # Method 2: Text content regex
        text_emails = self.extract_emails(html_content)
        emails.update(text_emails)
        
        # Filter and validate
        valid_emails = []
        for email in emails:
            if self._is_valid_business_email(email):
                valid_emails.append(email)
        
        return list(set(valid_emails))
    
    def _extract_contact_info(self, soup) -> Dict:
        """Extract additional contact information"""
        
        contact_info = {}
        
        # Phone numbers
        phone_pattern = r'(\+?1?[-.\s]?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4})'
        text_content = soup.get_text()
        phones = re.findall(phone_pattern, text_content)
        if phones:
            contact_info['phones'] = list(set(phones))
        
        return contact_info
    
    def _extract_business_info(self, soup) -> Dict:
        """Extract business/company information"""
        
        business_info = {}
        
        # Company name from title
        title = soup.find('title')
        if title:
            business_info['page_title'] = title.get_text().strip()
        
        # Description from meta tags
        description = soup.find('meta', attrs={'name': 'description'})
        if description:
            business_info['description'] = description.get('content', '').strip()
        
        return business_info
    
    def _is_valid_business_email(self, email: str) -> bool:
        """Check if email looks like a valid business email"""
        
        if not email or '@' not in email:
            return False
        
        # Skip obvious non-business emails
        skip_patterns = [
            'noreply', 'no-reply', 'donotreply', 'example.com',
            'test.com', 'localhost'
        ]
        
        email_lower = email.lower()
        for pattern in skip_patterns:
            if pattern in email_lower:
                return False
        
        return True
    
    def _combine_results(self, main_result: Dict, contact_pages: List[Dict], social_results: Dict) -> Dict:
        """Combine results from all scraping methods"""
        
        combined = {
            "emails": set(main_result.get('emails', [])),
            "social_handles": main_result.get('social_handles', {}),
            "contact_info": main_result.get('contact_info', {}),
            "business_info": main_result.get('business_info', {}),
            "contact_pages_found": len(contact_pages)
        }
        
        # Add emails from contact pages
        for page_result in contact_pages:
            combined["emails"].update(page_result.get('emails', []))
        
        # Add social media results
        combined["social_handles"].update(social_results)
        
        # Convert emails set back to list
        combined["emails"] = list(combined["emails"])
        
        return combined
