"""
Venue and promoter scraper for booking contacts
"""
import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin, urlparse
import ipaddress
import socket
from app.utils.email_utils import decode_obfuscated_email, validate_email_address

def validate_url_for_ssrf(venue_url):
    """
    Validate URL to prevent Server-Side Request Forgery (SSRF)
    """
    parsed_url = urlparse(venue_url)
    if parsed_url.scheme not in ('http', 'https'):
        raise ValueError(f"Invalid URL scheme: {parsed_url.scheme}")

    # Block private IP ranges
    hostname = parsed_url.hostname
    if hostname:
        try:
            # Check if hostname resolves to a private IP
            ip_addresses = socket.getaddrinfo(hostname, None)
            for addr_info in ip_addresses:
                ip = ipaddress.ip_address(addr_info[4][0])
                if ip.is_private or ip.is_loopback or ip.is_reserved or ip.is_link_local:
                    raise ValueError(f"Blocked private/reserved IP: {ip}")
        except socket.gaierror:
            # Hostname could not be resolved, which is fine
            pass
        except ValueError as e:
            # Re-raise the blockage error
            raise
        else:
            # Check against common private hostnames if not an IP
            if hostname in ['localhost', 'local', 'internal'] or hostname.endswith(('.local', '.internal', '.svc')):
                raise ValueError(f"Blocked private hostname: {hostname}")

def extract_venue_emails(venue_url):
    """
    Extract booking and contact emails from venue websites
    """
    try:
        # Validate URL to prevent SSRF
        validate_url_for_ssrf(venue_url)

        headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; ArtistPromoBot/1.0)',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        }

        response = requests.get(venue_url, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
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
        
        return list(set(validated_emails))  # Remove duplicates
        
    except Exception as e:
        print(f"Error extracting emails from venue {venue_url}: {str(e)}")
        return []

def extract_booking_info(venue_url):
    """
    Extract comprehensive booking information from venue
    """
    try:
        # Validate URL to prevent SSRF
        validate_url_for_ssrf(venue_url)

        headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; ArtistPromoBot/1.0)',
        }

        response = requests.get(venue_url, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        booking_info = {
            'emails': [],
            'phone_numbers': [],
            'booking_contact': '',
            'booking_department': '',
            'requirements': [],
            'rates': [],
            'capacity': None,
            'location': ''
        }
        
        # Extract text content
        text_content = soup.get_text()
        
        # Extract emails
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        raw_emails = re.findall(email_pattern, text_content)
        for email in raw_emails:
            normalized_email = decode_obfuscated_email(email)
            if validate_email_address(normalized_email):
                booking_info['emails'].append(normalized_email)
        
        # Extract phone numbers
        phone_patterns = [
            r'\+?1?[ -.]?\(?[0-9]{3}\)?[ -.]?[0-9]{3}[ -.]?[0-9]{4}',
            r'\(\d{3}\)\s*\d{3}-\d{4}',
            r'\d{3}-\d{3}-\d{4}'
        ]
        
        for pattern in phone_patterns:
            phones = re.findall(pattern, text_content)
            booking_info['phone_numbers'].extend(phones)
        
        # Extract booking contact names
        contact_patterns = [
            r'(?:booking contact|bookings?|contact person|agent|representative):\s*([A-Za-z\s]+)',
            r'(?:contact|reach out to)\s+([A-Za-z\s]+)(?:\s+at\b|\s+for\b)',
            r'(?:booking\s+inquiries?\s+to|contact\s+for\s+booking)\s+([A-Za-z\s]+)'
        ]
        
        for pattern in contact_patterns:
            matches = re.findall(pattern, text_content, re.IGNORECASE)
            if matches:
                booking_info['booking_contact'] = matches[0].strip()
                break
        
        # Extract capacity
        capacity_matches = re.findall(r'capacity[:\s]+(\d+(?:,\d+)?)', text_content, re.IGNORECASE)
        if capacity_matches:
            try:
                booking_info['capacity'] = int(capacity_matches[0].replace(',', ''))
            except (ValueError, TypeError) as e:
                # Log the failure for debugging
                print(f"Failed to parse capacity from '{capacity_matches[0]}': {str(e)}")
                # Leave booking_info['capacity'] as None
        
        # Extract location
        location_matches = re.findall(r'located in[:\s]+([A-Za-z\s,]+)', text_content, re.IGNORECASE)
        if location_matches:
            booking_info['location'] = location_matches[0].strip()
        
        # Extract special requirements
        req_patterns = [
            r'(?:requirements?|needs?|must|should include):\s*([^.]+)',
            r'(?:technical\s+rider|equipment\s+needs?):\s*([^.]+)'
        ]
        
        for pattern in req_patterns:
            matches = re.findall(pattern, text_content, re.IGNORECASE)
            booking_info['requirements'].extend(matches)
        
        # Remove duplicates
        booking_info['emails'] = list(set(booking_info['emails']))
        booking_info['phone_numbers'] = list(set(booking_info['phone_numbers']))
        
        return booking_info
        
    except Exception as e:
        print(f"Error extracting booking info from venue {venue_url}: {str(e)}")
        return {
            'emails': [],
            'phone_numbers': [],
            'booking_contact': '',
            'booking_department': '',
            'requirements': [],
            'rates': [],
            'capacity': None,
            'location': ''
        }

def extract_promoter_roster(promoter_url):
    """
    Extract roster of artists from promoter/booking agency websites
    """
    try:
        # Validate URL to prevent SSRF
        validate_url_for_ssrf(promoter_url)

        headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; ArtistPromoBot/1.0)',
        }

        response = requests.get(promoter_url, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        roster_info = {
            'artists': [],
            'contact_emails': [],
            'booking_info': {}
        }
        
        # Look for artist names in common elements
        artist_selectors = [
            'a', 'span', 'div', 'li', '.artist', '.act', '.performer', '.roster-item'
        ]
        
        for selector in artist_selectors:
            elements = soup.select(selector)
            for element in elements:
                text = element.get_text().strip()
                # Look for potential artist names (usually mixed case, no numbers)
                if len(text) > 2 and len(text.split()) <= 4 and not any(char.isdigit() for char in text):
                    # Filter out common non-artist words
                    common_words = {'the', 'and', 'or', 'of', 'in', 'on', 'at', 'to', 'for', 'with', 'by', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might', 'must', 'can', 'home', 'about', 'contact', 'services', 'products', 'news', 'events', 'calendar', 'tickets', 'shows', 'booking', 'bookings', 'management', 'press', 'media', 'social', 'follow', 'connect', 'subscribe', 'newsletter', 'privacy', 'terms', 'policy', 'copyright', 'rights', 'all', 'reserved'}
                    words = text.lower().split()
                    if not all(word in common_words for word in words):
                        roster_info['artists'].append(text)
        
        # Extract contact emails
        text_content = soup.get_text()
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        raw_emails = re.findall(email_pattern, text_content)
        
        for email in raw_emails:
            normalized_email = decode_obfuscated_email(email)
            if validate_email_address(normalized_email):
                roster_info['contact_emails'].append(normalized_email)
        
        # Remove duplicates
        roster_info['artists'] = list(set(roster_info['artists']))
        roster_info['contact_emails'] = list(set(roster_info['contact_emails']))
        
        return roster_info
        
    except Exception as e:
        print(f"Error extracting promoter roster from {promoter_url}: {str(e)}")
        return {
            'artists': [],
            'contact_emails': [],
            'booking_info': {}
        }

def find_venue_booking_pages(base_url):
    """
    Find common booking page URLs on a venue's website
    """
    common_booking_paths = [
        '/booking', '/bookings', '/contact', '/contact-us', '/contactus',
        '/submit', '/submission', '/submissions', '/gigs', '/events',
        '/artist-submission', '/booking-request', '/hire-us', '/partnerships'
    ]
    
    booking_pages = []
    
    for path in common_booking_paths:
        try:
            url = urljoin(base_url, path)

            # Validate URL to prevent SSRF
            try:
                validate_url_for_ssrf(url)
            except ValueError:
                # Skip URLs that fail SSRF validation
                continue

            headers = {'User-Agent': 'Mozilla/5.0 (compatible; ArtistPromoBot/1.0)'}
            response = requests.head(url, headers=headers, timeout=10)

            if response.status_code == 200:
                booking_pages.append(url)
        except Exception as e:
            if isinstance(e, (KeyboardInterrupt, SystemExit)):
                raise
            # Log the error for debugging
            print(f"Error checking booking path {url}: {str(e)}")
            continue
    
    return booking_pages