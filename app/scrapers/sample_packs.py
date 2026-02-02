"""
Sample pack and producer credit scraper
"""
import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin, urlparse
from app.utils.email_utils import decode_obfuscated_email, validate_email_address

def extract_sample_pack_producer_info(pack_url):
    """
    Extract producer and contact information from sample pack websites
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; ArtistPromoBot/1.0)'
        }
        
        response = requests.get(pack_url, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        pack_info = {
            'producers': [],
            'producer_emails': [],
            'social_links': [],
            'contact_info': [],
            'sample_pack_details': {}
        }
        
        # Get all text content
        text_content = soup.get_text()
        
        # Extract emails using multiple patterns
        email_patterns = [
            r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
            r'([a-zA-Z0-9._%+-]+\s*(?:\[at\]|\(at\)|@)\s*[a-zA-Z0-9.-]+\s*(?:\[dot\]|\(dot\)|\.)\s*[a-zA-Z]{2,})'
        ]
        
        emails = []
        for pattern in email_patterns:
            found_emails = re.findall(pattern, text_content, re.IGNORECASE)
            emails.extend(found_emails)
        
        # Normalize and validate emails
        validated_emails = []
        for email in emails:
            normalized_email = decode_obfuscated_email(email)
            if validate_email_address(normalized_email):
                validated_emails.append(normalized_email)
        
        pack_info['producer_emails'] = list(set(validated_emails))  # Remove duplicates
        
        # Extract producer names from various sources
        name_patterns = [
            r'(?:produced by|created by|composed by|written by)\s+([A-Za-z\s\-\']+)',
            r'(?:producer|composer|writer|artist)\s*:?\s*([A-Za-z\s\-\']+)',
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
                    pack_info['producers'].append(cleaned_match)
        
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
        pack_info['producers'] = list(set(pack_info['producers']))
        pack_info['producer_emails'] = list(set(pack_info['producer_emails']))
        pack_info['social_links'] = list(set(pack_info['social_links']))
        
        return pack_info
        
    except Exception as e:
        print(f"Error extracting sample pack info from {pack_url}: {str(e)}")
        return {
            'producers': [],
            'producer_emails': [],
            'social_links': [],
            'contact_info': [],
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
            'content_count': r'(?:contains|includes|features)\s*(\d+)\s*(?:sounds?|samples?|loops?)',
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
                continue  # Skip malformed JSON
        
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

def find_sample_pack_sites(artist_name):
    """
    Find sample pack sites that might feature the artist
    """
    search_terms = [
        f"{artist_name} sample pack",
        f"{artist_name} samples",
        f"{artist_name} loops",
        f"{artist_name} sound pack",
        f"{artist_name} producer pack"
    ]
    
    # This would typically involve search engine queries
    # For now, return empty with note about implementation
    print(f"Sample pack search for '{artist_name}' requires search engine integration")
    return []

def extract_bandcamp_artist_samples(bandcamp_url):
    """
    Extract sample pack or collaboration info from Bandcamp artist pages
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; ArtistPromoBot/1.0)'
        }
        
        response = requests.get(bandcamp_url, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        bandcamp_info = {
            'featured_producers': [],
            'collaborators': [],
            'contact_emails': [],
            'social_links': [],
            'related_artists': []
        }
        
        # Look for featured collaborators or producers
        text_content = soup.get_text()
        
        # Extract emails
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        raw_emails = re.findall(email_pattern, text_content)
        
        for email in raw_emails:
            normalized_email = decode_obfuscated_email(email)
            if validate_email_address(normalized_email):
                bandcamp_info['contact_emails'].append(normalized_email)
        
        # Look for collaborator patterns
        collab_patterns = [
            r'(?:featuring|ft\.?|with)\s+([A-Za-z\s\-\']+)',
            r'(?:collaboration with|in collaboration)\s+([A-Za-z\s\-\']+)',
            r'(?:produced by|mixed by|mastered by)\s+([A-Za-z\s\-\']+)',
            r'(?:guest|special appearance by)\s+([A-Za-z\s\-\']+)',
            r'(?:remixed by|remix by)\s+([A-Za-z\s\-\']+)',
            r'(?:featuring vocals by|vocalist)\s+([A-Za-z\s\-\']+)',
            r'(?:instrumental by|instruments by)\s+([A-Za-z\s\-\']+)',
        ]
        
        for pattern in collab_patterns:
            matches = re.findall(pattern, text_content, re.IGNORECASE)
            for match in matches:
                # Clean up the match
                cleaned_match = match.strip()
                if len(cleaned_match) > 2:  # Avoid single letters
                    bandcamp_info['collaborators'].append(cleaned_match)
        
        # Extract social links
        social_patterns = [
            r'(?:https?://)?(?:www\.)?instagram\.com/[a-zA-Z0-9_.]+',
            r'(?:https?://)?(?:www\.)?twitter\.com/[a-zA-Z0-9_]+',
            r'(?:https?://)?(?:www\.)?facebook\.com/[a-zA-Z0-9_.]+',
            r'(?:https?://)?(?:www\.)?soundcloud\.com/[a-zA-Z0-9_-]+',
            r'(?:https?://)?(?:www\.)?youtube\.com/@?[a-zA-Z0-9_-]+',
            r'(?:https?://)?(?:www\.)?linkedin\.com/[a-zA-Z0-9_.]+',
            r'(?:https?://)?(?:www\.)?tiktok\.com/@[a-zA-Z0-9_.]+'
        ]
        
        for pattern in social_patterns:
            matches = re.findall(pattern, text_content, re.IGNORECASE)
            bandcamp_info['social_links'].extend(matches)
        
        # Remove duplicates
        bandcamp_info['collaborators'] = list(set(bandcamp_info['collaborators']))
        bandcamp_info['contact_emails'] = list(set(bandcamp_info['contact_emails']))
        bandcamp_info['social_links'] = list(set(bandcamp_info['social_links']))
        
        return bandcamp_info
        
    except Exception as e:
        print(f"Error extracting Bandcamp info from {bandcamp_url}: {str(e)}")
        return {
            'featured_producers': [],
            'collaborators': [],
            'contact_emails': [],
            'social_links': [],
            'related_artists': []
        }

def extract_producer_credit_from_daw_projects(project_url):
    """
    Extract producer credits from DAW project sharing sites (like Splice, Loopcloud, etc.)
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; ArtistPromoBot/1.0)'
        }
        
        response = requests.get(project_url, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        project_info = {
            'project_creators': [],
            'contributors': [],
            'producer_emails': [],
            'project_details': {}
        }
        
        # Look for creator/contributor information
        creator_selectors = [
            '.creator', '.author', '.producer', '.artist', '.user',
            '[data-creator]', '[data-author]', '[data-producer]'
        ]
        
        for selector in creator_selectors:
            elements = soup.select(selector)
            for element in elements:
                text = element.get_text().strip()
                if text and len(text) > 2:
                    project_info['project_creators'].append(text)
        
        # Extract from JSON-LD or script tags
        script_tags = soup.find_all('script', type='application/ld+json')
        for script in script_tags:
            try:
                import json
                data = json.loads(script.string)
                
                # Look for creator/contributor info in structured data
                if 'creator' in data:
                    if isinstance(data['creator'], list):
                        for creator in data['creator']:
                            if isinstance(creator, dict) and 'name' in creator:
                                project_info['project_creators'].append(creator['name'])
                            elif isinstance(creator, str):
                                project_info['project_creators'].append(creator)
                    elif isinstance(data['creator'], dict) and 'name' in data['creator']:
                        project_info['project_creators'].append(data['creator']['name'])
                    elif isinstance(data['creator'], str):
                        project_info['project_creators'].append(data['creator'])
                
                if 'contributor' in data:
                    if isinstance(data['contributor'], list):
                        for contrib in data['contributor']:
                            if isinstance(contrib, dict) and 'name' in contrib:
                                project_info['contributors'].append(contrib['name'])
                            elif isinstance(contrib, str):
                                project_info['contributors'].append(contrib)
                    elif isinstance(data['contributor'], dict) and 'name' in data['contributor']:
                        project_info['contributors'].append(data['contributor']['name'])
                    elif isinstance(data['contributor'], str):
                        project_info['contributors'].append(data['contributor'])
                        
            except:
                continue  # Skip malformed JSON
        
        # Extract from page text
        text_content = soup.get_text()
        
        # Extract emails
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        raw_emails = re.findall(email_pattern, text_content)
        
        for email in raw_emails:
            normalized_email = decode_obfuscated_email(email)
            if validate_email_address(normalized_email):
                project_info['producer_emails'].append(normalized_email)
        
        # Remove duplicates
        project_info['project_creators'] = list(set(project_info['project_creators']))
        project_info['contributors'] = list(set(project_info['contributors']))
        project_info['producer_emails'] = list(set(project_info['producer_emails']))
        
        return project_info
        
    except Exception as e:
        print(f"Error extracting DAW project credits from {project_url}: {str(e)}")
        return {
            'project_creators': [],
            'contributors': [],
            'producer_emails': [],
            'project_details': {}
        }

def batch_extract_sample_pack_contacts(urls):
    """
    Batch extract contacts from multiple sample pack sources
    """
    all_contacts = {
        'sources_processed': [],
        'total_producers': [],
        'total_emails': [],
        'total_social_links': [],
        'pack_details': []
    }
    
    for url in urls:
        try:
            if 'splice' in url.lower():
                result = extract_splice_contributors(url)
            elif any(site in url.lower() for site in ['sample', 'loop', 'pack']):
                result = extract_sample_pack_producer_info(url)
            elif 'soundcloud' in url.lower() or 'bandcamp' in url.lower():
                result = extract_bandcamp_artist_samples(url)
            else:
                # Default to general sample pack extraction
                result = extract_sample_pack_producer_info(url)
            
            all_contacts['sources_processed'].append({
                'url': url,
                'producers': result.get('producers', []) + result.get('contributors', []),
                'emails': result.get('producer_emails', []),
                'social_links': result.get('social_links', []),
                'details': result.get('sample_pack_details', {}) if 'sample_pack_details' in result else result.get('pack_details', {})
            })
            
            # Aggregate all results
            all_contacts['total_producers'].extend(result.get('producers', []))
            all_contacts['total_producers'].extend(result.get('contributors', []))
            all_contacts['total_emails'].extend(result.get('producer_emails', []))
            all_contacts['total_social_links'].extend(result.get('social_links', []))
            if 'sample_pack_details' in result:
                all_contacts['pack_details'].append(result['sample_pack_details'])
            if 'pack_details' in result:
                all_contacts['pack_details'].append(result['pack_details'])
                
        except Exception as e:
            print(f"Error processing sample pack source {url}: {str(e)}")
            all_contacts['sources_processed'].append({
                'url': url,
                'error': str(e)
            })
    
    # Remove duplicates
    all_contacts['total_producers'] = list(set(all_contacts['total_producers']))
    all_contacts['total_emails'] = list(set(all_contacts['total_emails']))
    all_contacts['total_social_links'] = list(set(all_contacts['total_social_links']))
    
    return all_contacts