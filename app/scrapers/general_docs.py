"""
General search and document processing scraper
"""
import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin, urlparse
from app.utils.email_utils import decode_obfuscated_email, validate_email_address
import PyPDF2
import io
import asyncio
import aiohttp

def extract_contact_from_press_kit(pdf_url):
    """
    Extract contact information from artist press kits (PDFs)
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; ArtistPromoBot/1.0)'
        }
        
        response = requests.get(pdf_url, headers=headers, timeout=30)
        response.raise_for_status()
        
        pdf_content = io.BytesIO(response.content)
        pdf_reader = PyPDF2.PdfReader(pdf_content)
        
        press_kit_info = {
            'contacts': [],
            'emails': [],
            'social_links': [],
            'company_info': [],
            'bio_text': '',
            'press_quotes': []
        }
        
        # Extract text from all pages
        full_text = ""
        for page in pdf_reader.pages:
            full_text += page.extract_text() + "\n"
        
        # Extract emails
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        raw_emails = re.findall(email_pattern, full_text)
        
        for email in raw_emails:
            normalized_email = decode_obfuscated_email(email)
            if validate_email_address(normalized_email):
                press_kit_info['emails'].append(normalized_email)
        
        # Extract social media links
        social_patterns = [
            r'(?:https?://)?(?:www\.)?instagram\.com/[a-zA-Z0-9_.]+',
            r'(?:https?://)?(?:www\.)?twitter\.com/[a-zA-Z0-9_]+',
            r'(?:https?://)?(?:www\.)?facebook\.com/[a-zA-Z0-9_.]+',
            r'(?:https?://)?(?:www\.)?linkedin\.com/[a-zA-Z0-9_.]+',
            r'(?:https?://)?(?:www\.)?youtube\.com/@?[a-zA-Z0-9_-]+',
            r'(?:https?://)?(?:www\.)?tiktok\.com/@[a-zA-Z0-9_.]+',
            r'(?:https?://)?(?:www\.)?soundcloud\.com/[a-zA-Z0-9_-]+',
            r'(?:https?://)?(?:www\.)?bandcamp\.com/[a-zA-Z0-9_-]+',
            r'(?:https?://)?(?:www\.)?spotify\.com/(?:artist|user)/[a-zA-Z0-9_-]+'
        ]
        
        for pattern in social_patterns:
            matches = re.findall(pattern, full_text, re.IGNORECASE)
            press_kit_info['social_links'].extend(matches)
        
        # Extract contact names and positions
        name_patterns = [
            r'(?:contact|reach out to|for booking|press contact)\s*:\s*([A-Za-z\s\-\'\.]+)',
            r'(?:manager|booking|representative)\s*:\s*([A-Za-z\s\-\'\.]+)',
            r'(?:[A-Z][a-z]+\s+[A-Z][a-z]+)(?:\s+(?:manager|agent|representative|booking|press))',
            r'(?:manager|agent|representative|booking|press)\s+([A-Za-z\s\-\'\.]+)',
            r'(?:contact\s+person|primary\s+contact)\s*:\s*([A-Za-z\s\-\'\.]+)'
        ]
        
        for pattern in name_patterns:
            matches = re.findall(pattern, full_text, re.IGNORECASE)
            for match in matches:
                cleaned_match = re.sub(r'\s+', ' ', match.strip())
                if len(cleaned_match) > 3:  # Avoid short matches
                    press_kit_info['contacts'].append(cleaned_match)
        
        # Extract company information
        company_patterns = [
            r'(?:management|label|agency|company)\s*:\s*([A-Za-z0-9\s\-\'\.&,]+)',
            r'(?:represented by|managed by|signed to)\s+([A-Za-z0-9\s\-\'\.&,]+)',
            r'([A-Za-z0-9\s\-\'\.&,]+)(?:\s+(?:Inc|LLC|Ltd|Corp|Group|Records|Management|Agency|Label))',
            r'(?:under|with|affiliated with)\s+([A-Za-z0-9\s\-\'\.&,]+)'
        ]
        
        for pattern in company_patterns:
            matches = re.findall(pattern, full_text, re.IGNORECASE)
            for match in matches:
                cleaned_match = re.sub(r'\s+', ' ', match.strip())
                if len(cleaned_match) > 3:
                    press_kit_info['company_info'].append(cleaned_match)
        
        # Extract bio/quote sections
        bio_patterns = [
            r'(?:biography|bio|about the artist|artist bio)[:\s\n]+([A-Za-z0-9\s\-\'\.!,?;:()\[\]"\']+?)(?:\n\s*\n|##|\Z)',
            r'(?:press quote|testimonial)[:\s\n]+([A-Za-z0-9\s\-\'\.!,?;:()\[\]"\']+?)(?:\n\s*\n|##|\Z)',
            r'"([^"]{50,300})"[\s\n]*[-\u2013\u2014]\s*([A-Za-z\s\-\'\.]+)'  # Quotes with attribution
        ]
        
        for pattern in bio_patterns:
            matches = re.findall(pattern, full_text, re.IGNORECASE | re.DOTALL)
            for match in matches:
                if isinstance(match, tuple):
                    # For quote patterns with attribution
                    quote, attrib = match
                    press_kit_info['press_quotes'].append({
                        'quote': quote.strip(),
                        'attribution': attrib.strip()
                    })
                else:
                    # For bio patterns
                    bio_text = match.strip()
                    if len(bio_text) > 50:  # Only add substantial bios
                        press_kit_info['bio_text'] += bio_text + " "
        
        # Remove duplicates
        press_kit_info['contacts'] = list(set(press_kit_info['contacts']))
        press_kit_info['emails'] = list(set(press_kit_info['emails']))
        press_kit_info['social_links'] = list(set(press_kit_info['social_links']))
        press_kit_info['company_info'] = list(set(press_kit_info['company_info']))
        
        return press_kit_info
        
    except Exception as e:
        print(f"Error extracting contact from press kit {pdf_url}: {str(e)}")
        return {
            'contacts': [],
            'emails': [],
            'social_links': [],
            'company_info': [],
            'bio_text': '',
            'press_quotes': []
        }

def extract_contact_from_blog_article(blog_url):
    """
    Extract contact information from blog articles and music journalism
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; ArtistPromoBot/1.0)'
        }
        
        response = requests.get(blog_url, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        blog_contacts = {
            'author': None,
            'author_email': None,
            'interviewed_artist_contacts': [],
            'label_representatives': [],
            'publicist_info': [],
            'social_links': [],
            'affiliate_links': []
        }
        
        # Extract author information
        author_selectors = [
            '.author', '.byline', '.wp-block-post-author-name', 
            '[class*="author"]', '[class*="byline"]', '.post-author'
        ]
        
        for selector in author_selectors:
            element = soup.select_one(selector)
            if element:
                blog_contacts['author'] = element.get_text().strip()
                break
        
        # Extract text content
        text_content = soup.get_text()
        
        # Extract emails
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        raw_emails = re.findall(email_pattern, text_content)
        
        for email in raw_emails:
            normalized_email = decode_obfuscated_email(email)
            if validate_email_address(normalized_email):
                # Try to categorize based on context
                text_lower = text_content.lower()
                if any(keyword in text_lower for keyword in ['author', 'writer', 'journalist', 'editor']):
                    blog_contacts['author_email'] = normalized_email
                elif any(keyword in text_lower for keyword in ['publicist', 'press', 'manager', 'booking']):
                    blog_contacts['publicist_info'].append(normalized_email)
                else:
                    # Default to publicist for music industry context
                    blog_contacts['publicist_info'].append(normalized_email)
        
        # Extract names of people mentioned in interviews
        name_patterns = [
            r'(?:interview with|featuring|speaking to)\s+([A-Z][a-z]+\s+[A-Z][a-z]+)',
            r'(?:[A-Z][a-z]+\s+[A-Z][a-z]+)(?:\s+on\s+|talks\s+about|discusses)',
            r'(?:quoted\s+as\s+saying|mentioned\s+that)\s+"[^"]+"\s+(?:by|from)\s+([A-Z][a-z]+\s+[A-Z][a-z]+)',
            r'(?:contact|reach out to|connect with)\s+([A-Z][a-z]+\s+[A-Z][a-z]+)',
            r'(?:manager|publicist|booking agent)\s+([A-Z][a-z]+\s+[A-Z][a-z]+)'
        ]
        
        for pattern in name_patterns:
            matches = re.findall(pattern, text_content, re.IGNORECASE)
            for match in matches:
                cleaned_match = re.sub(r'\s+', ' ', match.strip())
                if len(cleaned_match) > 3:
                    if any(keyword in pattern.lower() for keyword in ['manager', 'publicist', 'agent', 'booking']):
                        blog_contacts['label_representatives'].append(cleaned_match)
                    else:
                        blog_contacts['interviewed_artist_contacts'].append(cleaned_match)
        
        # Extract social links
        social_patterns = [
            r'(?:https?://)?(?:www\.)?instagram\.com/[a-zA-Z0-9_.]+',
            r'(?:https?://)?(?:www\.)?twitter\.com/[a-zA-Z0-9_]+',
            r'(?:https?://)?(?:www\.)?facebook\.com/[a-zA-Z0-9_.]+',
            r'(?:https?://)?(?:www\.)?linkedin\.com/[a-zA-Z0-9_.]+',
            r'(?:https?://)?(?:www\.)?youtube\.com/@?[a-zA-Z0-9_-]+',
            r'(?:https?://)?(?:www\.)?tiktok\.com/@[a-zA-Z0-9_.]+',
            r'(?:https?://)?(?:www\.)?soundcloud\.com/[a-zA-Z0-9_-]+',
            r'(?:https?://)?(?:www\.)?bandcamp\.com/[a-zA-Z0-9_-]+',
            r'(?:https?://)?(?:www\.)?spotify\.com/(?:artist|user)/[a-zA-Z0-9_-]+'
        ]
        
        for pattern in social_patterns:
            matches = re.findall(pattern, text_content, re.IGNORECASE)
            blog_contacts['social_links'].extend(matches)
        
        # Extract affiliate/related links
        for link in soup.find_all('a', href=True):
            href = link['href']
            if any(domain in href for domain in ['amazon', 'itunes', 'spotify', 'youtube']):
                blog_contacts['affiliate_links'].append(href)
        
        return blog_contacts
        
    except Exception as e:
        print(f"Error extracting contact from blog {blog_url}: {str(e)}")
        return {
            'author': None,
            'author_email': None,
            'interviewed_artist_contacts': [],
            'label_representatives': [],
            'publicist_info': [],
            'social_links': [],
            'affiliate_links': []
        }

def extract_contact_from_podcast_page(podcast_url):
    """
    Extract contact information from podcast pages and show notes
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; ArtistPromoBot/1.0)'
        }
        
        response = requests.get(podcast_url, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        podcast_contacts = {
            'hosts': [],
            'producers': [],
            'booking_contact': None,
            'email_contacts': [],
            'social_links': [],
            'affiliate_partners': [],
            'guest_management': []
        }
        
        # Extract host information
        host_selectors = [
            '.host', '.producer', '.creator', '.team', '.staff',
            '[class*="host"]', '[class*="producer"]', '[class*="creator"]',
            '.podcast-host', '.show-host', '.producer-name'
        ]
        
        for selector in host_selectors:
            elements = soup.select(selector)
            for element in elements:
                text = element.get_text().strip()
                if text and len(text) > 2:
                    # Look for names (capitalized words)
                    name_matches = re.findall(r'([A-Z][a-z]+\s+[A-Z][a-z]+)', text)
                    for name in name_matches:
                        if 'host' in selector or 'host' in text.lower():
                            podcast_contacts['hosts'].append(name)
                        elif 'producer' in selector or 'producer' in text.lower():
                            podcast_contacts['producers'].append(name)
                        else:
                            # Default to host for music industry podcasts
                            podcast_contacts['hosts'].append(name)
        
        # Extract from text content
        text_content = soup.get_text()
        
        # Extract emails
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        raw_emails = re.findall(email_pattern, text_content)
        
        for email in raw_emails:
            normalized_email = decode_obfuscated_email(email)
            if validate_email_address(normalized_email):
                # Categorize based on context
                if any(keyword in text_content.lower() for keyword in ['booking', 'contact', 'inquiries']):
                    podcast_contacts['booking_contact'] = normalized_email
                elif any(keyword in text_content.lower() for keyword in ['producer', 'host', 'team']):
                    podcast_contacts['email_contacts'].append(normalized_email)
                else:
                    podcast_contacts['email_contacts'].append(normalized_email)
        
        # Extract contact names
        contact_patterns = [
            r'(?:contact|reach out to|get in touch with)\s+([A-Z][a-z]+\s+[A-Z][a-z]+)',
            r'(?:host|producer|creator)\s+([A-Z][a-z]+\s+[A-Z][a-z]+)',
            r'(?:managed by|represented by)\s+([A-Z][a-z]+\s+[A-Z][a-z]+)',
            r'(?:booking\s+inquiries\s+to|contact\s+for\s+booking)\s+([A-Z][a-z]+\s+[A-Z][a-z]+)'
        ]
        
        for pattern in contact_patterns:
            matches = re.findall(pattern, text_content, re.IGNORECASE)
            for match in matches:
                cleaned_match = re.sub(r'\s+', ' ', match.strip())
                if len(cleaned_match) > 3:
                    if any(keyword in pattern.lower() for keyword in ['booking', 'contact']):
                        podcast_contacts['booking_contact'] = cleaned_match
                    elif any(keyword in pattern.lower() for keyword in ['host', 'producer']):
                        podcast_contacts['hosts'].append(cleaned_match)
                    else:
                        podcast_contacts['guest_management'].append(cleaned_match)
        
        # Extract social links
        social_patterns = [
            r'(?:https?://)?(?:www\.)?instagram\.com/[a-zA-Z0-9_.]+',
            r'(?:https?://)?(?:www\.)?twitter\.com/[a-zA-Z0-9_]+',
            r'(?:https?://)?(?:www\.)?facebook\.com/[a-zA-Z0-9_.]+',
            r'(?:https?://)?(?:www\.)?linkedin\.com/[a-zA-Z0-9_.]+',
            r'(?:https?://)?(?:www\.)?youtube\.com/@?[a-zA-Z0-9_-]+',
            r'(?:https?://)?(?:www\.)?tiktok\.com/@[a-zA-Z0-9_.]+',
            r'(?:https?://)?(?:www\.)?soundcloud\.com/[a-zA-Z0-9_-]+',
            r'(?:https?://)?(?:www\.)?bandcamp\.com/[a-zA-Z0-9_-]+',
            r'(?:https?://)?(?:www\.)?spotify\.com/(?:artist|user)/[a-zA-Z0-9_-]+',
            r'(?:https?://)?(?:www\.)?anchor\.fm/[a-zA-Z0-9_-]+',
            r'(?:https?://)?(?:www\.)?podcasts\.apple\.com/[a-zA-Z0-9/-_]+'
        ]
        
        for pattern in social_patterns:
            matches = re.findall(pattern, text_content, re.IGNORECASE)
            podcast_contacts['social_links'].extend(matches)
        
        # Extract affiliate partners
        partner_patterns = [
            r'(?:sponsored by|in partnership with|presented by)\s+([A-Za-z0-9\s\-\'\.&,]+)',
            r'(?:affiliated with|supported by)\s+([A-Za-z0-9\s\-\'\.&,]+)',
            r'(?:[A-Z][a-z\s\-\'\.&,]+)(?:\s+(?:Inc|LLC|Ltd|Corp|Group|Records|Management|Agency|Label))'
        ]
        
        for pattern in partner_patterns:
            matches = re.findall(pattern, text_content, re.IGNORECASE)
            for match in matches:
                cleaned_match = re.sub(r'\s+', ' ', match.strip())
                if len(cleaned_match) > 3:
                    podcast_contacts['affiliate_partners'].append(cleaned_match)
        
        # Remove duplicates
        podcast_contacts['hosts'] = list(set(podcast_contacts['hosts']))
        podcast_contacts['producers'] = list(set(podcast_contacts['producers']))
        podcast_contacts['email_contacts'] = list(set(podcast_contacts['email_contacts']))
        podcast_contacts['social_links'] = list(set(podcast_contacts['social_links']))
        podcast_contacts['affiliate_partners'] = list(set(podcast_contacts['affiliate_partners']))
        podcast_contacts['guest_management'] = list(set(podcast_contacts['guest_management']))
        
        return podcast_contacts
        
    except Exception as e:
        print(f"Error extracting contact from podcast {podcast_url}: {str(e)}")
        return {
            'hosts': [],
            'producers': [],
            'booking_contact': None,
            'email_contacts': [],
            'social_links': [],
            'affiliate_partners': [],
            'guest_management': []
        }

def extract_contact_from_news_article(news_url):
    """
    Extract contact information from music news articles
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; ArtistPromoBot/1.0)'
        }
        
        response = requests.get(news_url, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        news_contacts = {
            'reporters': [],
            'publicists_mentioned': [],
            'label_representatives': [],
            'booking_agents': [],
            'contact_emails': [],
            'social_links': [],
            'company_affiliations': []
        }
        
        # Extract reporter/author
        author_selectors = [
            '.author', '.byline', '.by-author', '.wp-block-post-author-name',
            '[class*="author"]', '[class*="byline"]', '.article-author'
        ]
        
        for selector in author_selectors:
            element = soup.select_one(selector)
            if element:
                text = element.get_text().strip()
                if text and len(text) > 2:
                    # Look for names
                    name_matches = re.findall(r'([A-Z][a-z]+\s+[A-Z][a-z]+)', text)
                    for name in name_matches:
                        news_contacts['reporters'].append(name)
        
        # Extract from article text
        text_content = soup.get_text()
        
        # Extract emails
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        raw_emails = re.findall(email_pattern, text_content)
        
        for email in raw_emails:
            normalized_email = decode_obfuscated_email(email)
            if validate_email_address(normalized_email):
                # Categorize based on context in article
                text_lower = text_content.lower()
                if any(keyword in text_lower for keyword in ['publicist', 'press', 'pr firm']):
                    news_contacts['publicists_mentioned'].append(normalized_email)
                elif any(keyword in text_lower for keyword in ['booking', 'agent', 'manager']):
                    news_contacts['booking_agents'].append(normalized_email)
                elif any(keyword in text_lower for keyword in ['label', 'representative', 'rep']):
                    news_contacts['label_representatives'].append(normalized_email)
                else:
                    news_contacts['contact_emails'].append(normalized_email)
        
        # Extract names of people mentioned
        name_patterns = [
            r'(?:publicist|press agent|pr rep)\s+([A-Z][a-z]+\s+[A-Z][a-z]+)',
            r'(?:booking agent|manager|representative)\s+([A-Z][a-z]+\s+[A-Z][a-z]+)',
            r'(?:at\s+|with\s+|from\s+)([A-Z][a-z\s\-\'\.]+)(?:\s+for\b|\s+said\b)',
            r'(?:[A-Z][a-z]+\s+[A-Z][a-z]+)(?:\s+of\s+|works\s+at\s+|represents\s+)',
            r'(?:contact\s+for|reach out to)\s+([A-Z][a-z]+\s+[A-Z][a-z]+)'
        ]
        
        for pattern in name_patterns:
            matches = re.findall(pattern, text_content, re.IGNORECASE)
            for match in matches:
                cleaned_match = re.sub(r'\s+', ' ', match.strip())
                if len(cleaned_match) > 3:
                    if any(keyword in pattern.lower() for keyword in ['publicist', 'press', 'pr']):
                        news_contacts['publicists_mentioned'].append(cleaned_match)
                    elif any(keyword in pattern.lower() for keyword in ['booking', 'agent', 'manager']):
                        news_contacts['booking_agents'].append(cleaned_match)
                    elif any(keyword in pattern.lower() for keyword in ['label', 'rep', 'representative']):
                        news_contacts['label_representatives'].append(cleaned_match)
                    else:
                        news_contacts['label_representatives'].append(cleaned_match)  # Default for music industry
        
        # Extract company affiliations
        company_patterns = [
            r'(?:at\s+|with\s+|from\s+|works\s+for\s+|signed\s+to\s+)([A-Z][a-zA-Z0-9\s\-\'\.&,]+?)(?:\s+Inc\b|\s+LLC\b|\s+Ltd\b|\s+Corp\b|\s+Group\b|\s+Records\b|\s+Management\b|\s+Agency\b|\s+Label\b|\s+Promotion\b|\s+Studio\b|\s+Company\b|\s+and\s+|\s+or\s+|\s+for\b|\s+on\b|\s+the\b|\s+in\b|\s+with\b|\s+at\b|\s+is\b|\s+was\b|\s+will\b|\s+has\b|\s+had\b|\s+have\b|\s+do\b|\s+does\b|\s+did\b|\s+can\b|\s+could\b|\s+should\b|\s+would\b|\s+must\b|\s+might\b|\s+may\b|\s+will\b|\s+shall\b|\s+to\b|\s+for\b|\s+of\b|\s+in\b|\s+on\b|\s+at\b|\s+by\b|\s+with\b|\s+from\b|\s+to\b|\s+into\b|\s+during\b|\s+including\b|\s+until\b|\s+against\b|\s+among\b|\s+throughout\b|\s+despite\b|\s+towards\b|\s+upon\b|\s+concerning\b|\s+about\b|\s+like\b|\s+through\b|\s+over\b|\s+before\b|\s+between\b|\s+after\b|\s+since\b|\s+without\b|\s+under\b|\s+within\b|\s+along\b|\s+following\b|\s+across\b|\s+behind\b|\s+beyond\b|\s+plus\b|\s+near\b|\s+since\b)',
            r'([A-Z][a-zA-Z0-9\s\-\'\.&,]+?)(?:\s+Inc\b|\s+LLC\b|\s+Ltd\b|\s+Corp\b|\s+Group\b|\s+Records\b|\s+Management\b|\s+Agency\b|\s+Label\b|\s+Promotion\b|\s+Studio\b|\s+Company\b)'
        ]
        
        for pattern in company_patterns:
            matches = re.findall(pattern, text_content, re.IGNORECASE)
            for match in matches:
                cleaned_match = re.sub(r'\s+', ' ', match.strip())
                if len(cleaned_match) > 3:
                    news_contacts['company_affiliations'].append(cleaned_match)
        
        # Extract social links
        social_patterns = [
            r'(?:https?://)?(?:www\.)?instagram\.com/[a-zA-Z0-9_.]+',
            r'(?:https?://)?(?:www\.)?twitter\.com/[a-zA-Z0-9_]+',
            r'(?:https?://)?(?:www\.)?facebook\.com/[a-zA-Z0-9_.]+',
            r'(?:https?://)?(?:www\.)?linkedin\.com/[a-zA-Z0-9_.]+',
            r'(?:https?://)?(?:www\.)?youtube\.com/@?[a-zA-Z0-9_-]+',
            r'(?:https?://)?(?:www\.)?tiktok\.com/@[a-zA-Z0-9_.]+',
            r'(?:https?://)?(?:www\.)?soundcloud\.com/[a-zA-Z0-9_-]+',
            r'(?:https?://)?(?:www\.)?bandcamp\.com/[a-zA-Z0-9_-]+',
            r'(?:https?://)?(?:www\.)?spotify\.com/(?:artist|user)/[a-zA-Z0-9_-]+'
        ]
        
        for pattern in social_patterns:
            matches = re.findall(pattern, text_content, re.IGNORECASE)
            news_contacts['social_links'].extend(matches)
        
        # Remove duplicates
        news_contacts['reporters'] = list(set(news_contacts['reporters']))
        news_contacts['publicists_mentioned'] = list(set(news_contacts['publicists_mentioned']))
        news_contacts['label_representatives'] = list(set(news_contacts['label_representatives']))
        news_contacts['booking_agents'] = list(set(news_contacts['booking_agents']))
        news_contacts['contact_emails'] = list(set(news_contacts['contact_emails']))
        news_contacts['social_links'] = list(set(news_contacts['social_links']))
        news_contacts['company_affiliations'] = list(set(news_contacts['company_affiliations']))
        
        return news_contacts
        
    except Exception as e:
        print(f"Error extracting contact from news article {news_url}: {str(e)}")
        return {
            'reporters': [],
            'publicists_mentioned': [],
            'label_representatives': [],
            'booking_agents': [],
            'contact_emails': [],
            'social_links': [],
            'company_affiliations': []
        }

def batch_extract_from_documents(urls):
    """
    Batch extract contacts from multiple document sources
    """
    all_contacts = {
        'sources_processed': [],
        'total_contacts': [],
        'total_emails': [],
        'total_companies': [],
        'total_social_links': []
    }
    
    for url in urls:
        try:
            if any(ext in url.lower() for ext in ['.pdf']):
                contacts = extract_contact_from_press_kit(url)
                source_type = 'press_kit'
            elif any(keyword in url.lower() for keyword in ['blog', 'article', 'journal']):
                contacts = extract_contact_from_blog_article(url)
                source_type = 'blog_article'
            elif any(keyword in url.lower() for keyword in ['podcast', 'episode', 'show']):
                contacts = extract_contact_from_podcast_page(url)
                source_type = 'podcast'
            elif any(keyword in url.lower() for keyword in ['news', 'magazine', 'publication']):
                contacts = extract_contact_from_news_article(url)
                source_type = 'news'
            else:
                # Default to blog article extraction for general web pages
                contacts = extract_contact_from_blog_article(url)
                source_type = 'general_web'
            
            all_contacts['sources_processed'].append({
                'url': url,
                'type': source_type,
                'contacts': contacts
            })
            
            # Aggregate all contacts
            all_contacts['total_contacts'].extend(contacts.get('contacts', []))
            all_contacts['total_contacts'].extend(contacts.get('hosts', []))
            all_contacts['total_contacts'].extend(contacts.get('producers', []))
            all_contacts['total_contacts'].extend(contacts.get('reporters', []))
            all_contacts['total_contacts'].extend(contacts.get('interviewed_artist_contacts', []))
            all_contacts['total_contacts'].extend(contacts.get('label_representatives', []))
            all_contacts['total_contacts'].extend(contacts.get('booking_agents', []))
            all_contacts['total_contacts'].extend(contacts.get('publicists_mentioned', []))
            all_contacts['total_contacts'].extend(contacts.get('guest_management', []))
            
            all_contacts['total_emails'].extend(contacts.get('emails', []))
            all_contacts['total_emails'].extend(contacts.get('email_contacts', []))
            all_contacts['total_emails'].extend([contacts.get('author_email')] if contacts.get('author_email') else [])
            all_contacts['total_emails'].extend(contacts.get('booking_contact') if isinstance(contacts.get('booking_contact'), list) else [contacts.get('booking_contact')] if contacts.get('booking_contact') else [])
            
            all_contacts['total_companies'].extend(contacts.get('company_info', []))
            all_contacts['total_companies'].extend(contacts.get('affiliate_partners', []))
            all_contacts['total_companies'].extend(contacts.get('company_affiliations', []))
            
            all_contacts['total_social_links'].extend(contacts.get('social_links', []))
            
        except Exception as e:
            print(f"Error processing document {url}: {str(e)}")
            all_contacts['sources_processed'].append({
                'url': url,
                'error': str(e)
            })
    
    # Remove duplicates
    all_contacts['total_contacts'] = list(set(all_contacts['total_contacts']))
    all_contacts['total_emails'] = list(set(all_contacts['total_emails']))
    if None in all_contacts['total_emails']:
        all_contacts['total_emails'].remove(None)  # Remove any None values
    all_contacts['total_companies'] = list(set(all_contacts['total_companies']))
    all_contacts['total_social_links'] = list(set(all_contacts['total_social_links']))
    
    return all_contacts