"""
Reverse image search and EXIF data scraper with SSRF protection
"""
import requests
import json
from PIL import Image
import ipaddress
from urllib.parse import urlparse
from PIL.ExifTags import TAGS, GPSTAGS
import io
import re
from urllib.parse import urljoin
from app.utils.email_utils import decode_obfuscated_email, validate_email_address

def extract_exif_data(image_path_or_url):
    """
    Extract EXIF data from an image, including GPS coordinates and contact info
    """
    import socket
    import ipaddress
    from urllib.parse import urlparse
    
    try:
        # Handle both local paths and URLs
        if image_path_or_url.startswith(('http://', 'https://')):
            # Validate URL to prevent SSRF
            parsed_url = urlparse(image_path_or_url)
            
            # Check scheme
            if parsed_url.scheme not in ['http', 'https']:
                raise ValueError(f"Invalid URL scheme: {parsed_url.scheme}")
            
            # Resolve hostname to IP and check if it's safe
            try:
                addr_info = socket.getaddrinfo(parsed_url.hostname, None)
                for res in addr_info:
                    ip = ipaddress.ip_address(res[4][0])
                    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved:
                        raise ValueError(f"Private/reserved IP address blocked: {ip}")
            except socket.gaierror:
                raise ValueError(f"Could not resolve hostname: {parsed_url.hostname}")
            
            response = requests.get(image_path_or_url, timeout=30)
            response.raise_for_status()
            image_data = io.BytesIO(response.content)
            file_handle = None
        else:
            # For local files, open with proper file handle
            file_handle = open(image_path_or_url, 'rb')
            image_data = file_handle

        try:
            # Open image and extract EXIF
            image = Image.open(image_data)
            exif_data = image._getexif()

            if not exif_data:
                return {}

            # Parse EXIF data
            parsed_exif = {}
            for tag_id, value in exif_data.items():
                tag = TAGS.get(tag_id, tag_id)
                parsed_exif[tag] = value

            # Extract GPS info if available
            gps_info = {}
            if 'GPSInfo' in parsed_exif:
                for key in parsed_exif['GPSInfo'].keys():
                    name = GPSTAGS.get(key, key)
                    gps_info[name] = parsed_exif['GPSInfo'][key]
                parsed_exif['GPS'] = gps_info

            return parsed_exif
        finally:
            # Close file handle if opened
            if file_handle:
                file_handle.close()

    except Exception as e:
        print(f"Error extracting EXIF data from {image_path_or_url}: {str(e)}")
        return {}

def extract_exif_emails(image_path_or_url):
    """
    Extract any email addresses from EXIF data
    """
    exif_data = extract_exif_data(image_path_or_url)
    
    emails = []
    # Check common EXIF fields that might contain contact info
    contact_fields = ['Artist', 'Copyright', 'ImageDescription', 'UserComment', 'Software']
    
    for field in contact_fields:
        if field in exif_data and exif_data[field]:
            text_content = str(exif_data[field])
            found_emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text_content)
            
            for email in found_emails:
                normalized_email = decode_obfuscated_email(email)
                if validate_email_address(normalized_email):
                    emails.append(normalized_email)
    
    return list(set(emails))  # Remove duplicates

def reverse_image_search_google_vision(image_url, api_key):
    """
    Perform reverse image search using Google Vision API Web Detection
    """
    try:
        import base64
        import socket
        import ipaddress
        from urllib.parse import urlparse
        
        # Validate URL to prevent SSRF
        parsed_url = urlparse(image_url)
        if parsed_url.scheme not in ['http', 'https']:
            raise ValueError(f"Invalid URL scheme: {parsed_url.scheme}")
        
        # Ensure a hostname is present for network requests
        if not parsed_url.hostname:
            raise ValueError(f"URL does not contain a valid hostname: {image_url}")

        try:
            # Resolve hostname to IP addresses. The 'None' for service (port) is intentional,
            # as we only care about the IP address for SSRF protection, not port-level resolution here.
            addr_info = socket.getaddrinfo(parsed_url.hostname, None)
            for res in addr_info:
                ip = ipaddress.ip_address(res[4][0]) # res[4][0] is the IP address string
                if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved:
                    raise ValueError(f"Private/reserved IP address blocked: {ip}")
        except socket.gaierror:
            raise ValueError(f"Could not resolve hostname: {parsed_url.hostname}")
        except Exception as e: # Catch any other unexpected errors during IP validation
            raise ValueError(f"IP validation error for {parsed_url.hostname}: {str(e)}")
        
        # Download image content
        response = requests.get(image_url, timeout=30)
        response.raise_for_status()
        
        # Encode image content to base64
        encoded_image = base64.b64encode(response.content).decode('utf-8')
        
        # Prepare Vision API request
        vision_url = "https://vision.googleapis.com/v1/images:annotate"
        headers = {
            'Content-Type': 'application/json',
        }
        
        body = {
            'requests': [{
                'image': {
                    'content': encoded_image
                },
                'features': [
                    {
                        'type': 'WEB_DETECTION',
                        'maxResults': 10
                    }
                ]
            }]
        }
        
        params = {
            'key': api_key
        }
        
        response = requests.post(vision_url, headers=headers, json=body, params=params, timeout=30)
        response.raise_for_status()
        
        results = response.json()
        
        pages_with_image = []
        if 'responses' in results and len(results['responses']) > 0:
            web_detection = results['responses'][0].get('webDetection', {})
            
            # Get pages with matching images
            if 'pagesWithMatchingImages' in web_detection:
                for page in web_detection['pagesWithMatchingImages']:
                    pages_with_image.append({
                        'url': page.get('url'),
                        'title': page.get('pageTitle'),
                        'snippet': page.get('description'),
                        'score': page.get('score')
                    })
                    
            # Get partial matching images
            if 'partialMatchingImages' in web_detection:
                for img in web_detection['partialMatchingImages']:
                    pages_with_image.append({
                        'url': img.get('url'),
                        'title': img.get('pageTitle'),
                        'snippet': img.get('description'),
                        'score': img.get('score')
                    })
                    
            # Get full matching images
            if 'fullMatchingImages' in web_detection:
                for img in web_detection['fullMatchingImages']:
                    pages_with_image.append({
                        'url': img.get('url'),
                        'title': img.get('pageTitle'),
                        'snippet': img.get('description'),
                        'score': img.get('score')
                    })

        return pages_with_image

    except Exception as e:
        print(f"Error in Google Vision reverse image search: {str(e)}")
        return []


def reverse_image_search_google(image_url, api_key, search_engine_id):
    """
    Perform reverse image search using Google Custom Search API
    Note: This is a fallback method since Google Custom Search doesn't truly support reverse image search by URL
    """
    try:
        # Since Google Custom Search API doesn't support true reverse image search by URL,
        # we'll use Google Vision API instead if api_key is provided
        if api_key:
            return reverse_image_search_google_vision(image_url, api_key)
        
        # Fallback: Use Google Custom Search API with image URL as query
        search_url = "https://www.googleapis.com/customsearch/v1"

        params = {
            'key': api_key,
            'cx': search_engine_id,
            'searchType': 'image',
            'imgSize': 'large',
            'num': 10
        }

        # For image URL search - this is not true reverse image search but the best we can do with this API
        params['q'] = f"image:{image_url}"

        response = requests.get(search_url, params=params, timeout=30)
        response.raise_for_status()

        results = response.json()

        pages_with_image = []
        if 'items' in results:
            for item in results['items']:
                pages_with_image.append({
                    'url': item.get('link'),
                    'title': item.get('title'),
                    'snippet': item.get('snippet'),
                    'image_url': item.get('image', {}).get('thumbnailLink')
                })

        return pages_with_image

    except Exception as e:
        print(f"Error in Google reverse image search: {str(e)}")
        return []

def reverse_image_search_yandex(image_url):
    """
    Perform reverse image search using Yandex (alternative method)
    """
    # This would require implementing Yandex reverse image search
    # which may involve web scraping their interface
    # For now, return empty result
    print("Yandex reverse image search requires web scraping implementation")
    return []

def extract_contact_from_reverse_search(image_url, google_api_key=None, search_engine_id=None):
    """
    Extract contact information from reverse image search results
    """
    import socket
    import ipaddress
    from urllib.parse import urlparse, urljoin
    import requests

    def validate_url_for_ssrf(url):
        parsed_url = urlparse(url)
        if parsed_url.scheme not in ['http', 'https']:
            raise ValueError(f"Invalid URL scheme: {parsed_url.scheme}")

        if not parsed_url.hostname:
            raise ValueError(f"URL does not contain a valid hostname: {url}")

        try:
            addr_info = socket.getaddrinfo(parsed_url.hostname, None)
            for res in addr_info:
                ip = ipaddress.ip_address(res[4][0])
                if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved:
                    raise ValueError(f"Private/reserved IP address blocked: {ip}")
        except socket.gaierror:
            raise ValueError(f"Could not resolve hostname: {parsed_url.hostname}")
        except Exception as e:
            raise ValueError(f"IP validation error for {parsed_url.hostname}: {str(e)}")

    try:
        # Validate initial URL
        validate_url_for_ssrf(image_url)

        # Download image with redirect validation
        response = requests.get(image_url, allow_redirects=False, timeout=10)
        while response.is_redirect:
            next_url = response.headers['Location']
            if next_url.startswith(('http://', 'https://')):
                validate_url_for_ssrf(next_url)
            else:
                # Handle relative redirects
                next_url = urljoin(image_url, next_url)
                validate_url_for_ssrf(next_url)

            response = requests.get(next_url, allow_redirects=False, timeout=10)

        # Initialize contact info dictionary
        contact_info = {
            'emails': [],
            'phone_numbers': [],
            'websites': [],
            'social_profiles': [],
            'possible_names': [],
            'locations': []
        }
        
        # Perform reverse image search
        search_results = []
        
        if google_api_key and search_engine_id:
            search_results.extend(
                reverse_image_search_google(image_url, google_api_key, search_engine_id)
            )
        
        # Process search results for contact information
        for result in search_results:
            page_url = result.get('url')
            if page_url:
                # Extract contact info from each page that contains the image
                page_contacts = extract_contact_info_from_page(page_url)
                contact_info['emails'].extend(page_contacts.get('emails', []))
                contact_info['websites'].append(page_url)
                contact_info['social_profiles'].extend(page_contacts.get('social_profiles', []))
                contact_info['possible_names'].extend(page_contacts.get('names', []))
        
        # Also check EXIF data from the original image
        exif_emails = extract_exif_emails(image_url)
        contact_info['emails'].extend(exif_emails)
        
        # Remove duplicates
        contact_info['emails'] = list(set(contact_info['emails']))
        contact_info['websites'] = list(set(contact_info['websites']))
        contact_info['social_profiles'] = list(set(contact_info['social_profiles']))
        contact_info['possible_names'] = list(set(contact_info['possible_names']))
        
        return contact_info
    except Exception as e:
        print(f"Error extracting contact from reverse search: {str(e)}")
        return {
            'emails': [],
            'phone_numbers': [],
            'websites': [],
            'social_profiles': [],
            'possible_names': [],
            'locations': []
        }

def extract_contact_info_from_page(url):
    """
    Extract contact information from a webpage
    """
    import socket
    import ipaddress
    from urllib.parse import urlparse
    
    try:
        # Validate URL to prevent SSRF
        parsed_url = urlparse(url)
        
        # Check scheme
        if parsed_url.scheme not in ['http', 'https']:
            raise ValueError(f"Invalid URL scheme: {parsed_url.scheme}")
        
        # Resolve hostname to IP and check if it's safe
        try:
            addr_info = socket.getaddrinfo(parsed_url.hostname, None)
            for res in addr_info:
                ip = ipaddress.ip_address(res[4][0])
                if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved:
                    raise ValueError(f"Private/reserved IP address blocked: {ip}")
        except socket.gaierror:
            raise ValueError(f"Could not resolve hostname: {parsed_url.hostname}")
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; ArtistPromoBot/1.0)'
        }

        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(response.text, 'html.parser')
        
        contact_data = {
            'emails': [],
            'social_profiles': [],
            'names': []
        }
        
        # Extract text content
        text_content = soup.get_text()
        
        # Find emails
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        raw_emails = re.findall(email_pattern, text_content)
        
        for email in raw_emails:
            normalized_email = decode_obfuscated_email(email)
            if validate_email_address(normalized_email):
                contact_data['emails'].append(normalized_email)
        
        # Find social media profiles
        social_patterns = [
            r'(?:https?://)?(?:www\.)?instagram\.com/([a-zA-Z0-9_.]+)',
            r'(?:https?://)?(?:www\.)?twitter\.com/([a-zA-Z0-9_]+)',
            r'(?:https?://)?(?:www\.)?facebook\.com/([a-zA-Z0-9_.]+)',
            r'(?:https?://)?(?:www\.)?linkedin\.com/(?:in|company)/([a-zA-Z0-9-_.]+)',
            r'(?:https?://)?(?:www\.)?youtube\.com/@?([a-zA-Z0-9_-]+)',
            r'(?:https?://)?(?:www\.)?tiktok\.com/@([a-zA-Z0-9_.]+)',
            r'(?:https?://)?(?:www\.)?soundcloud\.com/([a-zA-Z0-9_-]+)',
            r'(?:https?://)?(?:www\.)?bandcamp\.com/([a-zA-Z0-9_-]+)'
        ]
        
        for pattern in social_patterns:
            matches = re.findall(pattern, text_content, re.IGNORECASE)
            for match in matches:
                # Extract domain from pattern to construct proper URL
                if 'instagram' in pattern:
                    domain = 'instagram.com/'
                elif 'twitter' in pattern:
                    domain = 'twitter.com/'
                elif 'facebook' in pattern:
                    domain = 'facebook.com/'
                elif 'linkedin' in pattern:
                    domain = 'linkedin.com/'
                elif 'youtube' in pattern:
                    domain = 'youtube.com/'
                elif 'tiktok' in pattern:
                    domain = 'tiktok.com/'
                elif 'soundcloud' in pattern:
                    domain = 'soundcloud.com/'
                elif 'bandcamp' in pattern:
                    domain = 'bandcamp.com/'
                else:
                    domain = 'unknown.com/'  # fallback

                # For TikTok, we need to add the @ symbol to the profile URL
                if 'tiktok.com/' in domain and not match.startswith('@'):
                    profile_url = f"https://{domain}@{match}"
                else:
                    profile_url = f"https://{domain}{match}"
                contact_data['social_profiles'].append(profile_url)
        
        # Find possible names (simple heuristic - people names often have capital letters)
        # This is a basic implementation - in practice you'd want NLP name recognition
        name_candidates = re.findall(r'\b[A-Z][a-z]{1,20}\s+[A-Z][a-z]{1,20}\b', text_content)
        contact_data['names'].extend(name_candidates)
        
        return contact_data
        
    except Exception as e:
        print(f"Error extracting contact info from {url}: {str(e)}")
        return {
            'emails': [],
            'social_profiles': [],
            'names': []
        }

def batch_reverse_image_lookup(image_urls, google_api_key=None, search_engine_id=None):
    """
    Perform reverse image lookup for multiple images
    """
    results = []
    
    for image_url in image_urls:
        try:
            result = extract_contact_from_reverse_search(
                image_url, 
                google_api_key=google_api_key, 
                search_engine_id=search_engine_id
            )
            result['image_url'] = image_url
            results.append(result)
        except Exception as e:
            print(f"Error processing image {image_url}: {str(e)}")
            results.append({
                'image_url': image_url,
                'error': str(e),
                'emails': [],
                'websites': [],
                'social_profiles': [],
                'possible_names': [],
                'locations': []
            })
    
    return results

def extract_geolocation_from_image(image_path_or_url):
    """
    Extract geographic location from image EXIF data
    """
    try:
        exif_data = extract_exif_data(image_path_or_url)
        
        if 'GPS' in exif_data:
            gps = exif_data['GPS']
            
            # Convert GPS coordinates to decimal degrees
            lat = None
            lon = None
            
            if 'GPSLatitude' in gps and 'GPSLatitudeRef' in gps:
                lat = convert_gps_to_decimal(gps['GPSLatitude'], gps['GPSLatitudeRef'])
            
            if 'GPSLongitude' in gps and 'GPSLongitudeRef' in gps:
                lon = convert_gps_to_decimal(gps['GPSLongitude'], gps['GPSLongitudeRef'])
            
            if lat is not None and lon is not None:
                return {
                    'latitude': lat,
                    'longitude': lon,
                    'coordinates': f"{lat}, {lon}"
                }
        
        return None
        
    except Exception as e:
        print(f"Error extracting geolocation from {image_path_or_url}: {str(e)}")
        return None

def convert_gps_to_decimal(gps_coords, gps_ref):
    """
    Convert GPS coordinates from degrees/minutes/seconds to decimal
    """
    try:
        # GPS coordinates are typically stored as rational numbers (numerator/denominator)
        def dms_to_decimal(degrees, minutes, seconds, direction):
            decimal = degrees + (minutes / 60.0) + (seconds / 3600.0)
            if direction in ['S', 'W']:
                decimal *= -1
            return decimal
        
        if isinstance(gps_coords, tuple) and len(gps_coords) == 3:
            degrees, minutes, seconds = gps_coords
            # Handle rational numbers (numerator, denominator) with zero division check
            def safe_rational_to_float(rational):
                if isinstance(rational, tuple) and len(rational) >= 2 and rational[1] != 0:
                    return rational[0] / rational[1]
                return None  # Return None instead of 0 to indicate invalid GPS data

            if isinstance(degrees, tuple):
                degrees = safe_rational_to_float(degrees)
            if isinstance(minutes, tuple):
                minutes = safe_rational_to_float(minutes)
            if isinstance(seconds, tuple):
                seconds = safe_rational_to_float(seconds)

            if None in (degrees, minutes, seconds):
                return None

            return dms_to_decimal(float(degrees), float(minutes), float(seconds), gps_ref)
    
    except Exception as e:
        print(f"Error converting GPS coordinates: {str(e)}")
        return None

def find_artist_press_photos(artist_name):
    """
    Find press photos for an artist that might contain contact info in EXIF
    """
    # This would typically involve searching for press photos using search engines
    # For now, return empty list with a note about implementation
    print(f"Artist press photo search for '{artist_name}' requires search engine integration")
    return []

def extract_artist_contact_from_press_kit_images(press_kit_urls):
    """
    Extract contact information from images in press kits
    """
    all_contacts = {
        'emails': [],
        'locations': [],
        'possible_names': [],
        'associated_websites': []
    }
    
    for url in press_kit_urls:
        try:
            # This would involve downloading the press kit (PDF/ZIP) and extracting images
            # For now, we'll just note that this requires additional implementation
            print(f"Press kit image analysis for {url} requires archive extraction")
        except Exception as e:
            print(f"Error processing press kit {url}: {str(e)}")
    
    return all_contacts