"""
Extended scraper modules for the artist promotion pipeline
"""
import requests
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import whois
from PyPDF2 import PdfReader
import requests
from io import BytesIO
from app.utils.email_utils import decode_obfuscated_email, validate_email_address

def extract_ig_business_email(username):
    """Extract business email from Instagram profile"""
    # Note: Instagram's API access is restricted, so this is a simplified version
    # In production, you'd use Instagram's Business API or a reliable third-party service
    try:
        # This is a placeholder - actual implementation would require proper API access
        # or use a service like Instaloader
        import instaloader
        
        loader = instaloader.Instaloader()
        profile = instaloader.Profile.from_username(loader.context, username)
        
        if profile.business_email:
            if validate_email_address(profile.business_email):
                return profile.business_email
    except:
        pass
    return None

def extract_x_bio_emails(username):
    """Extract emails from X/Twitter bio using alternative methods"""
    # Since direct API access is limited, we'll use Nitter (as implemented in the pipeline)
    # This is a simplified version - the full implementation is in async_scraping.py
    try:
        # This would use the Nitter scraper from the pipeline
        from app.utils.async_scraping import scrape_nitter
        # For now, return empty list as this is already implemented in the pipeline
        return []
    except:
        return []

def extract_youtube_channel_emails(channel_id):
    """Extract emails from YouTube channel About page"""
    # This would use the Invidious scraper from the pipeline
    try:
        from app.utils.async_scraping import scrape_invidious_channel
        # For now, return empty list as this is already implemented in the pipeline
        return []
    except:
        return []

def extract_patreon_creator_info(username):
    """Extract contact info from Patreon creator page"""
    try:
        url = f"https://www.patreon.com/{username}"
        headers = {'User-Agent': 'Mozilla/5.0 (compatible; ArtistPromoBot/1.0)'}
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for contact information in various elements
            text_content = soup.get_text()
            
            # Extract emails
            emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text_content)
            validated_emails = []
            
            for email in emails:
                normalized_email = decode_obfuscated_email(email)
                if validate_email_address(normalized_email):
                    validated_emails.append(normalized_email)
            
            return list(set(validated_emails))  # Remove duplicates
            
    except Exception as e:
        print(f"Error extracting Patreon info for {username}: {str(e)}")
    
    return []

def extract_social_media_emails(url):
    """Generic function to extract emails from social media pages"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (compatible; ArtistPromoBot/1.0)'}
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            text_content = soup.get_text()
            
            # Extract emails
            emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text_content)
            validated_emails = []
            
            for email in emails:
                normalized_email = decode_obfuscated_email(email)
                if validate_email_address(normalized_email):
                    validated_emails.append(normalized_email)
            
            return list(set(validated_emails))
            
    except Exception as e:
        print(f"Error extracting emails from {url}: {str(e)}")
    
    return []