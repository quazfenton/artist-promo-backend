"""
Reverse image search and EXIF data scraper
"""
import requests
import json
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
import io
import re
from urllib.parse import urljoin
from app.utils.email_utils import decode_obfuscated_email, validate_email_address

def extract_exif_data(image_path_or_url):
    """
    Extract EXIF data from an image, including GPS coordinates and contact info
    """
    try:
        # Handle both local paths and URLs
        if image_path_or_url.startswith(('http://', 'https://')):
            response = requests.get(image_path_or_url)
            response.raise_for_status()
            image_data = io.BytesIO(response.content)
        else:
            image_data = image_path_or_url  # Local file path
        
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

def reverse_image_search_google(image_url, api_key, search_engine_id):
    """
    Perform reverse image search using Google Custom Search API
    """
    try:
        search_url = "https://www.googleapis.com/customsearch/v1"
        
        params = {
            'key': api_key,
            'cx': search_engine_id,
            'searchType': 'image',
            'imgSize': 'large',
            'num': 10
        }
        
        # For image URL search
        params['q'] = f"image:{image_url}"
        
        response = requests.get(search_url, params=params)
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
    contact_info = {
        'emails': [],
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

def extract_contact_info_from_page(url):
    """
    Extract contact information from a webpage
    """
    try:
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