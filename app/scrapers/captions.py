"""
Closed captions and transcript scraper
"""
import requests
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import json
import xml.etree.ElementTree as ET
from app.utils.email_utils import decode_obfuscated_email, validate_email_address

def extract_captions_emails(youtube_video_id):
    """
    Extract emails from YouTube video captions/transcripts
    """
    try:
        # Try to get captions in different languages
        caption_urls = [
            f"https://video.google.com/timedtext?lang=en&v={youtube_video_id}",
            f"https://video.google.com/timedtext?lang=en-US&v={youtube_video_id}",
            f"https://video.google.com/timedtext?lang=en-GB&v={youtube_video_id}",
        ]
        
        all_emails = []
        
        for url in caption_urls:
            try:
                response = requests.get(url)
                if response.status_code == 200:
                    # Parse the XML captions
                    root = ET.fromstring(response.text)
                    
                    # Extract text from all caption elements
                    caption_text = ""
                    for text_elem in root.findall('.//text'):
                        caption_text += " " + text_elem.text or ""
                    
                    # Find emails in the caption text
                    emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', caption_text)
                    
                    for email in emails:
                        normalized_email = decode_obfuscated_email(email)
                        if validate_email_address(normalized_email):
                            all_emails.append(normalized_email)
                    
                    break  # Successfully got captions, no need to try other languages
            except ET.ParseError:
                continue  # Try next language
        
        return list(set(all_emails))  # Remove duplicates
        
    except Exception as e:
        print(f"Error extracting emails from YouTube captions for video {video_id}: {str(e)}")
        return []

def extract_video_description_emails(video_url):
    """
    Extract emails from video descriptions on various platforms
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; ArtistPromoBot/1.0)'
        }
        
        response = requests.get(video_url, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Look for description elements
        description_selectors = [
            '[data-testid="video-description"]',
            '.video-description',
            '.description',
            '.ytd-video-secondary-info-renderer',  # YouTube
            '.player-video-details',  # Various platforms
            '.video-meta',
            '.video-info'
        ]
        
        description_text = ""
        for selector in description_selectors:
            elem = soup.select_one(selector)
            if elem:
                description_text = elem.get_text()
                break
        
        # If no specific description found, get all text
        if not description_text:
            description_text = soup.get_text()
        
        # Extract emails
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        raw_emails = re.findall(email_pattern, description_text)
        
        validated_emails = []
        for email in raw_emails:
            normalized_email = decode_obfuscated_email(email)
            if validate_email_address(normalized_email):
                validated_emails.append(normalized_email)
        
        return list(set(validated_emails))  # Remove duplicates
        
    except Exception as e:
        print(f"Error extracting emails from video description {video_url}: {str(e)}")
        return []

def extract_podcast_transcript_emails(podcast_url):
    """
    Extract emails from podcast transcripts
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; ArtistPromoBot/1.0)'
        }
        
        response = requests.get(podcast_url, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Look for transcript elements
        transcript_selectors = [
            '.transcript',
            '[class*="transcript"]',
            '.episode-transcript',
            '.podcast-transcript',
            '.show-notes',
            '[data-transcript]',
            '#transcript',
            '.content'
        ]
        
        transcript_text = ""
        for selector in transcript_selectors:
            elem = soup.select_one(selector)
            if elem:
                transcript_text += elem.get_text() + " "
        
        # If no transcript found, try to get main content
        if not transcript_text:
            main_content = soup.find('main') or soup.find('article') or soup.find('div', class_=re.compile(r'content|main|article'))
            if main_content:
                transcript_text = main_content.get_text()
        
        # Extract emails from transcript
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        raw_emails = re.findall(email_pattern, transcript_text)
        
        validated_emails = []
        for email in raw_emails:
            normalized_email = decode_obfuscated_email(email)
            if validate_email_address(normalized_email):
                validated_emails.append(normalized_email)
        
        return list(set(validated_emails))  # Remove duplicates
        
    except Exception as e:
        print(f"Error extracting emails from podcast transcript {podcast_url}: {str(e)}")
        return []

def extract_stream_chat_emails(stream_url):
    """
    Extract emails from live stream chat data (where available)
    """
    # This is more complex and platform-specific
    # For now, we'll focus on what we can get from the stream page itself
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; ArtistPromoBot/1.0)'
        }
        
        response = requests.get(stream_url, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract any emails from the stream page itself
        text_content = soup.get_text()
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        raw_emails = re.findall(email_pattern, text_content)
        
        validated_emails = []
        for email in raw_emails:
            normalized_email = decode_obfuscated_email(email)
            if validate_email_address(normalized_email):
                validated_emails.append(normalized_email)
        
        return list(set(validated_emails))  # Remove duplicates
        
    except Exception as e:
        print(f"Error extracting emails from stream page {stream_url}: {str(e)}")
        return []

def extract_video_platform_emails(platform_url):
    """
    Generic function to extract emails from video platform pages
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; ArtistPromoBot/1.0)'
        }
        
        response = requests.get(platform_url, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract text from various elements that might contain contact info
        contact_elements = soup.find_all(['div', 'span', 'p', 'section'], 
                                       attrs={'class': re.compile(r'contact|about|bio|description|info|links|social|follow|connect|reach|email|mail')})
        
        contact_text = ""
        for elem in contact_elements:
            contact_text += elem.get_text() + " "
        
        # Also get general page text as fallback
        if not contact_text:
            contact_text = soup.get_text()
        
        # Extract emails using multiple patterns
        email_patterns = [
            r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
            r'([a-zA-Z0-9._%+-]+[^a-zA-Z0-9._%+-])\s*(?:\[at\]|@|\(at\))\s*([a-zA-Z0-9.-]+[^a-zA-Z0-9.-])\s*(?:\[dot\]|\.|\(dot\))\s*([a-zA-Z]{2,})',
            r'([a-zA-Z0-9._%+-]+[^a-zA-Z0-9._%+-])\s*(?:at)\s*([a-zA-Z0-9.-]+[^a-zA-Z0-9.-])\s*(?:dot)\s*([a-zA-Z]{2,})'
        ]
        
        all_emails = []
        for pattern in email_patterns:
            matches = re.findall(pattern, contact_text)
            for match in matches:
                if isinstance(match, tuple):
                    # Handle obfuscated emails
                    email = f"{match[0].strip() if match[0] else ''}@{match[1].strip() if match[1] else ''}.{match[2].strip() if match[2] else ''}"
                    email = email.replace(' ', '')  # Remove spaces
                else:
                    email = match
                
                normalized_email = decode_obfuscated_email(email)
                if validate_email_address(normalized_email):
                    all_emails.append(normalized_email)
        
        # Direct pattern matching for clean emails
        direct_emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', contact_text)
        for email in direct_emails:
            normalized_email = decode_obfuscated_email(email)
            if validate_email_address(normalized_email):
                all_emails.append(normalized_email)
        
        return list(set(all_emails))  # Remove duplicates
        
    except Exception as e:
        print(f"Error extracting emails from video platform {platform_url}: {str(e)}")
        return []

def extract_youtube_channel_emails(channel_url):
    """
    Extract emails from YouTube channel pages
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; ArtistPromoBot/1.0)'
        }
        
        response = requests.get(channel_url, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Look for custom URL which might lead to business info
        # YouTube often has a "About" tab with contact info
        about_patterns = [
            r'business\s*:\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
            r'contact\s*:\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
            r'email\s*:\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
            r'booking\s*:\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
            r'press\s*:\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
            r'manager\s*:\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'
        ]
        
        page_text = soup.get_text()
        emails = []
        
        for pattern in about_patterns:
            matches = re.findall(pattern, page_text, re.IGNORECASE)
            for match in matches:
                normalized_email = decode_obfuscated_email(match)
                if validate_email_address(normalized_email):
                    emails.append(normalized_email)
        
        # Also look for regular email patterns
        regular_emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', page_text)
        for email in regular_emails:
            normalized_email = decode_obfuscated_email(email)
            if validate_email_address(normalized_email):
                emails.append(normalized_email)
        
        return list(set(emails))  # Remove duplicates
        
    except Exception as e:
        print(f"Error extracting emails from YouTube channel {channel_url}: {str(e)}")
        return []

def extract_video_comment_emails(video_url, max_comments=50):
    """
    Extract emails from video comments (where publicly accessible)
    Note: This may not work on all platforms due to API restrictions
    """
    try:
        # This is platform-dependent and may require specific APIs
        # For now, we'll just return an empty list with a note
        print(f"Comment scraping for {video_url} requires platform-specific API access")
        return []
        
    except Exception as e:
        print(f"Error extracting emails from video comments {video_url}: {str(e)}")
        return []

def scrape_video_platform_for_contacts(url):
    """
    Main function to scrape various video platforms for contact information
    """
    platform_info = {
        'url': url,
        'emails': [],
        'platform_type': None,
        'additional_info': {}
    }
    
    try:
        # Determine platform type
        if 'youtube.com' in url or 'youtu.be' in url:
            platform_info['platform_type'] = 'youtube'
            # Extract from video description
            platform_info['emails'].extend(extract_video_description_emails(url))
            
            # Try to get channel info if it's a video URL
            if '/watch' in url or 'youtu.be/' in url:
                # Extract channel URL from video page would require more complex parsing
                pass
                
        elif 'vimeo.com' in url:
            platform_info['platform_type'] = 'vimeo'
            platform_info['emails'].extend(extract_video_platform_emails(url))
            
        elif 'twitch.tv' in url:
            platform_info['platform_type'] = 'twitch'
            platform_info['emails'].extend(extract_video_platform_emails(url))
            
        elif 'soundcloud.com' in url:
            platform_info['platform_type'] = 'soundcloud'
            platform_info['emails'].extend(extract_video_platform_emails(url))
        
        # Remove duplicates
        platform_info['emails'] = list(set(platform_info['emails']))
        
        return platform_info
        
    except Exception as e:
        print(f"Error scraping video platform {url}: {str(e)}")
        return {
            'url': url,
            'emails': [],
            'platform_type': None,
            'additional_info': {'error': str(e)}
        }

def batch_extract_video_emails(video_urls):
    """
    Extract emails from multiple video URLs
    """
    all_results = []
    
    for url in video_urls:
        try:
            result = scrape_video_platform_for_contacts(url)
            all_results.append(result)
        except Exception as e:
            print(f"Error processing video URL {url}: {str(e)}")
            all_results.append({
                'url': url,
                'emails': [],
                'platform_type': None,
                'additional_info': {'error': str(e)}
            })
    
    return all_results