"""
Sample pack and producer credit scraper
"""
import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin
from app.utils.email_utils import decode_obfuscated_email, validate_email_address

def extract_sample_pack_contributors(pack_url):
    """
    Extract contributor information from sample pack websites
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; ArtistPromoBot/1.0)',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        }
        
        response = requests.get(pack_url, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        pack_info = {
            'contributors': [],
            'producer_emails': [],
            'contact_info': [],
            'social_links': [],
            'sample_pack_details': {}
        }
        
        # Get all text content
        text_content = soup.get_text()
        
        # Extract emails
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        raw_emails = re.findall(email_pattern, text_content)
        
        for email in raw_emails:
            normalized_email = decode_obfuscated_email(email)
            if validate_email_address(normalized_email):
                pack_info['producer_emails'].append(normalized_email)
        
        # Extract contributor names
        name_patterns = [
            r'(?:produced by|created by|composed by|written by)\s+([A-Za-z\s\-\']+)',
            r'(?:producer|composer|writer|artist)\s+:?\s+([A-Za-z\s\-\']+)',
            r'(?:featuring contributions from|with samples by)\s+([A-Za-z\s\-\']+)',
            r'(?:credited to|credited as)\s+([A-Za-z\s\-\']+)',
            r'(?:samples courtesy of|thanks to)\s+([A-Za-z\s\-\']+)',
            r'(?:sample pack by|pack produced by)\s+([A-Za-z\s\-\']+)',
            r'(?:artist|producer|composer):\s*([A-Za-z\s\-\']+)',
            r'(?:by\s+)([A-Za-z\s\-\']+)(?:\s+for|on|in|the|this)'
        ]
        
        for pattern in name_patterns:
            matches = re.findall(pattern, text_content, re.IGNORECASE)
            for match in matches:
                # Clean up the match
                cleaned_match = match.strip()
                if len(cleaned_match) > 2:  # Avoid single letters
                    pack_info['contributors'].append(cleaned_match)
        
        # Extract social media links
        social_patterns = [
            r'(?:https?://)?(?:www\.)?instagram\.com/[a-zA-Z0-9_.]+',
            r'(?:https?://)?(?:www\.)?twitter\.com/[a-zA-Z0-9_]+',
            r'(?:https?://)?(?:www\.)?facebook\.com/[a-zA-Z0-9_.]+',
            r'(?:https?://)?(?:www\.)?linkedin\.com/[a-zA-Z0-9_.]+',
            r'(?:https?://)?(?:www\.)?youtube\.com/@?[a-zA-Z0-9_-]+',
            r'(?:https?://)?(?:www\.)?soundcloud\.com/[a-zA-Z0-9_-]+',
            r'(?:https?://)?(?:www\.)?bandcamp\.com/[a-zA-Z0-9_-]+',
            r'(?:https?://)?(?:www\.)?spotify\.com/(?:artist|user)/[a-zA-Z0-9_-]+'
        ]
        
        for pattern in social_patterns:
            matches = re.findall(pattern, text_content, re.IGNORECASE)
            pack_info['social_links'].extend(matches)
        
        # Extract sample pack details
        detail_patterns = {
            'pack_name': r'(?:sample pack|sound pack|loop pack)\s+[\'"]([^\'"]+)[\'"]',
            'genre': r'(?:genre|style|type):\s*([A-Za-z\s\-,]+)',
            'bpm': r'(?:bpm|tempo):\s*(\d+)',
            'key': r'(?:key|musical key):\s*([A-G][#b]?(?:\s*m(?:inor)?|\s*M(?:ajor)?)?)',
            'samples_count': r'(?:contains|includes|features)\s*(\d+)\s*(?:samples?|loops?|sounds?)',
            'license': r'(?:license|usage rights|commercial license):\s*([A-Za-z\s]+)'
        }
        
        for key, pattern in detail_patterns.items():
            matches = re.findall(pattern, text_content, re.IGNORECASE)
            if matches:
                pack_info['sample_pack_details'][key] = matches[0].strip()
        
        # Remove duplicates
        pack_info['contributors'] = list(set(pack_info['contributors']))
        pack_info['producer_emails'] = list(set(pack_info['producer_emails']))
        pack_info['social_links'] = list(set(pack_info['social_links']))
        
        return pack_info
        
    except Exception as e:
        print(f"Error extracting sample pack contributors from {pack_url}: {str(e)}")
        return {
            'contributors': [],
            'producer_emails': [],
            'contact_info': [],
            'social_links': [],
            'sample_pack_details': {}
        }

def extract_sound_library_producers(library_url):
    """
    Extract producer information from sound library websites
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; ArtistPromoBot/1.0)',
        }
        
        response = requests.get(library_url, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        library_info = {
            'producers': [],
            'producer_emails': [],
            'producer_websites': [],
            'contact_info': [],
            'library_details': {}
        }
        
        # Get all text content
        text_content = soup.get_text()
        
        # Extract emails
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        raw_emails = re.findall(email_pattern, text_content)
        
        for email in raw_emails:
            normalized_email = decode_obfuscated_email(email)
            if validate_email_address(normalized_email):
                library_info['producer_emails'].append(normalized_email)
        
        # Extract producer names
        producer_patterns = [
            r'(?:producer|composer|sound designer|audio engineer)\s*:?\s*([A-Za-z\s\-\']+)',
            r'(?:created by|produced by|arranged by)\s+([A-Za-z\s\-\']+)',
            r'(?:credited to|featured producer)\s+([A-Za-z\s\-\']+)',
            r'(?:in association with|featuring work by)\s+([A-Za-z\s\-\']+)',
            r'(?:production by|produced in collaboration with)\s+([A-Za-z\s\-\']+)',
            r'(?:artist|producer|composer):\s*([A-Za-z\s\-\']+)',
            r'(?:samples by|sounds by|loops by)\s+([A-Za-z\s\-\']+)',
            r'(?:credited producer|featured artist)\s+([A-Za-z\s\-\']+)',
            r'(?:production team|creative team)\s*:\s*([A-Za-z\s\-\',]+)'
        ]
        
        for pattern in producer_patterns:
            matches = re.findall(pattern, text_content, re.IGNORECASE)
            for match in matches:
                # Split by comma in case multiple producers are listed
                producers = [p.strip() for p in match.split(',')]
                for producer in producers:
                    if len(producer) > 2:  # Avoid single letters
                        library_info['producers'].append(producer)
        
        # Extract producer websites
        website_patterns = [
            r'(?:website|personal site|portfolio):\s*(https?://[^\s<>"\']+)',
            r'(?:visit|check out|learn more at)\s+(https?://[^\s<>"\']+)',
            r'(?:personal website|producer site)\s+([https?://][^\s<>"\']+)',
        ]
        
        for pattern in website_patterns:
            matches = re.findall(pattern, text_content, re.IGNORECASE)
            library_info['producer_websites'].extend(matches)
        
        # Extract library details
        detail_patterns = {
            'library_name': r'(?:sound library|sample library|audio library)\s*[\'"]([^\'"]+)[\'"]',
            'category': r'(?:category|genre|style):\s*([A-Za-z\s\-,]+)',
            'content_count': r'(?:contains|includes|features)\s*(\d+)\s*(?:sounds?|samples?|loops?|instruments?)',
            'formats': r'(?:formats|supported formats):\s*([A-Za-z\s\-,]+)',
            'price': r'(?:price|cost|purchase price):\s*([$€£¥]\d+(?:\.\d{2})?)'
        }
        
        for key, pattern in detail_patterns.items():
            matches = re.findall(pattern, text_content, re.IGNORECASE)
            if matches:
                library_info['library_details'][key] = matches[0].strip()
        
        # Remove duplicates
        library_info['producers'] = list(set(library_info['producers']))
        library_info['producer_emails'] = list(set(library_info['producer_emails']))
        library_info['producer_websites'] = list(set(library_info['producer_websites']))
        
        return library_info
        
    except Exception as e:
        print(f"Error extracting sound library producers from {library_url}: {str(e)}")
        return {
            'producers': [],
            'producer_emails': [],
            'producer_websites': [],
            'contact_info': [],
            'library_details': {}
        }

def extract_splice_contributors(splice_url):
    """
    Extract contributor information from Splice sample pack pages
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; ArtistPromoBot/1.0)',
        }
        
        response = requests.get(splice_url, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        splice_info = {
            'contributors': [],
            'producer_emails': [],
            'social_links': [],
            'pack_details': {}
        }
        
        # Look for contributor information in common selectors
        contributor_selectors = [
            '.contributor', '.producer', '.artist', '.creator', 
            '[data-contributor]', '[data-producer]', '.credit'
        ]
        
        for selector in contributor_selectors:
            elements = soup.select(selector)
            for element in elements:
                text = element.get_text().strip()
                if text and len(text) > 2:
                    splice_info['contributors'].append(text)
        
        # Extract from script tags (Splice often stores data in JSON)
        script_tags = soup.find_all('script', type='application/json')
        for script in script_tags:
            try:
                import json
                data = json.loads(script.string)
                # Look for contributor information in JSON data
                if 'contributors' in data:
                    splice_info['contributors'].extend(data['contributors'])
                if 'producer' in data:
                    splice_info['contributors'].append(data['producer'])
                if 'authors' in data:
                    splice_info['contributors'].extend(data['authors'])
            except:
                continue
        
        # Get all text content for additional extraction
        text_content = soup.get_text()
        
        # Extract emails
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        raw_emails = re.findall(email_pattern, text_content)
        
        for email in raw_emails:
            normalized_email = decode_obfuscated_email(email)
            if validate_email_address(normalized_email):
                splice_info['producer_emails'].append(normalized_email)
        
        # Extract social links
        social_patterns = [
            r'(?:https?://)?(?:www\.)?instagram\.com/[a-zA-Z0-9_.]+',
            r'(?:https?://)?(?:www\.)?twitter\.com/[a-zA-Z0-9_]+',
            r'(?:https?://)?(?:www\.)?soundcloud\.com/[a-zA-Z0-9_-]+',
            r'(?:https?://)?(?:www\.)?youtube\.com/@?[a-zA-Z0-9_-]+',
            r'(?:https?://)?(?:www\.)?facebook\.com/[a-zA-Z0-9_.]+'
        ]
        
        for pattern in social_patterns:
            matches = re.findall(pattern, text_content, re.IGNORECASE)
            splice_info['social_links'].extend(matches)
        
        # Remove duplicates
        splice_info['contributors'] = list(set(splice_info['contributors']))
        splice_info['producer_emails'] = list(set(splice_info['producer_emails']))
        splice_info['social_links'] = list(set(splice_info['social_links']))
        
        return splice_info
        
    except Exception as e:
        print(f"Error extracting Splice contributors from {splice_url}: {str(e)}")
        return {
            'contributors': [],
            'producer_emails': [],
            'social_links': [],
            'pack_details': {}
        }

def find_sample_pack_sites(base_url):
    """
    Find sample pack sections on a website
    """
    common_pack_paths = [
        '/sample-packs', '/samples', '/loops', '/sounds', '/audio',
        '/sound-packs', '/sample-library', '/loop-library', '/drum-kits',
        '/presets', '/plugins', '/instruments', '/synths', '/samplers',
        '/libraries', '/collections', '/downloads', '/resources'
    ]
    
    pack_pages = []
    
    for path in common_pack_paths:
        try:
            url = urljoin(base_url, path)
            headers = {'User-Agent': 'Mozilla/5.0 (compatible; ArtistPromoBot/1.0)'}
            response = requests.head(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                pack_pages.append(url)
        except:
            continue
    
    return pack_pages