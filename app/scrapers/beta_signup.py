"""
Beta signup and early adopter scraper
"""
import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin
from app.utils.email_utils import decode_obfuscated_email, validate_email_address

def extract_beta_signup_emails(signup_page_url):
    """
    Extract emails from beta signup pages
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; ArtistPromoBot/1.0)',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        }
        
        response = requests.get(signup_page_url, headers=headers, timeout=30)
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
        print(f"Error extracting beta signup emails from {signup_page_url}: {str(e)}")
        return []

def extract_early_adopter_community_info(community_url):
    """
    Extract information from early adopter communities
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; ArtistPromoBot/1.0)',
        }
        
        response = requests.get(community_url, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        community_info = {
            'emails': [],
            'members': [],
            'contact_persons': [],
            'social_links': [],
            'platforms': []
        }
        
        # Extract text content
        text_content = soup.get_text()
        
        # Extract emails
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        raw_emails = re.findall(email_pattern, text_content)
        for email in raw_emails:
            normalized_email = decode_obfuscated_email(email)
            if validate_email_address(normalized_email):
                community_info['emails'].append(normalized_email)
        
        # Extract member names (common patterns in communities)
        name_patterns = [
            r'(?:member|user|participant):\s*([A-Za-z\s]+)',
            r'(?:contributor|early adopter)\s+([A-Za-z\s]+)',
            r'(?:community member|beta tester)\s+([A-Za-z\s]+)'
        ]

        for pattern in name_patterns:
            matches = re.findall(pattern, text_content, re.IGNORECASE)
            community_info['contact_persons'].extend(matches)
            community_info['members'].extend(matches)  # Also add to members list
        
        # Extract social media links
        social_patterns = [
            r'(?:https?://)?(?:www\.)?twitter\.com/[a-zA-Z0-9_]+',
            r'(?:https?://)?(?:www\.)?instagram\.com/[a-zA-Z0-9_.]+',
            r'(?:https?://)?(?:www\.)?linkedin\.com/[a-zA-Z0-9_.]+',
            r'(?:https?://)?(?:www\.)?github\.com/[a-zA-Z0-9_.]+',
            r'(?:https?://)?(?:www\.)?facebook\.com/[a-zA-Z0-9_.]+'
        ]
        
        for pattern in social_patterns:
            matches = re.findall(pattern, text_content, re.IGNORECASE)
            community_info['social_links'].extend(matches)
        
        # Extract platform mentions
        platform_patterns = [
            r'(?:using|testing|feedback on)\s+([A-Za-z\s]+)',
            r'(?:platform|tool|software)\s+([A-Za-z\s]+)',
            r'(?:early access to)\s+([A-Za-z\s]+)'
        ]
        
        for pattern in platform_patterns:
            matches = re.findall(pattern, text_content, re.IGNORECASE)
            community_info['platforms'].extend(matches)
        
        # Remove duplicates
        community_info['emails'] = list(set(community_info['emails']))
        community_info['contact_persons'] = list(set(community_info['contact_persons']))
        community_info['members'] = list(set(community_info['members']))  # Also deduplicate members
        community_info['social_links'] = list(set(community_info['social_links']))
        community_info['platforms'] = list(set(community_info['platforms']))
        
        return community_info
        
    except Exception as e:
        print(f"Error extracting early adopter community info from {community_url}: {str(e)}")
        return {
            'emails': [],
            'members': [],
            'contact_persons': [],
            'social_links': [],
            'platforms': []
        }

def find_beta_programs(base_url):
    """
    Find beta program signup pages on a website
    """
    common_beta_paths = [
        '/beta', '/beta-signup', '/early-access', '/earlyaccess', '/waitlist',
        '/signup', '/register', '/join', '/community', '/feedback', '/testing',
        '/alpha', '/prelaunch', '/launch', '/new', '/innovation', '/labs'
    ]
    
    beta_pages = []
    
    for path in common_beta_paths:
        try:
            url = urljoin(base_url, path)
            headers = {'User-Agent': 'Mozilla/5.0 (compatible; ArtistPromoBot/1.0)'}
            response = requests.head(url, headers=headers, timeout=10)

            if response.status_code == 200:
                beta_pages.append(url)
        except Exception:
            pass
    
    return beta_pages

def extract_discord_beta_community_info(discord_invite_url):
    """
    Extract information from Discord beta communities
    Note: This requires a Discord bot to access the API
    """
    # This is a placeholder - actual implementation would require:
    # 1. Discord bot token
    # 2. Proper OAuth2 setup
    # 3. Channel access permissions
    
    print(f"Discord community scraping requires bot setup for: {discord_invite_url}")
    return {
        'emails': [],
        'members': [],
        'contact_persons': [],
        'social_links': [],
        'platforms': []
    }

def extract_forum_beta_discussions(forum_url):
    """
    Extract beta discussion information from forums
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; ArtistPromoBot/1.0)',
        }
        
        response = requests.get(forum_url, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        forum_info = {
            'emails': [],
            'discussions': [],
            'participants': [],
            'beta_mentions': []
        }
        
        # Extract all text content
        text_content = soup.get_text()
        
        # Extract emails
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        raw_emails = re.findall(email_pattern, text_content)
        for email in raw_emails:
            normalized_email = decode_obfuscated_email(email)
            if validate_email_address(normalized_email):
                forum_info['emails'].append(normalized_email)
        
        # Look for beta-related discussions
        beta_keywords = [
            r'beta', r'early access', r'preview', r'alpha', r'testing', 
            r'feedback', r'pre-release', r'prototype', r'pilot', r'trial'
        ]
        
        for keyword in beta_keywords:
            matches = re.findall(rf'({keyword}.*?)(?:\.|\n|$)', text_content, re.IGNORECASE)
            forum_info['beta_mentions'].extend(matches)
        
        # Extract participant information
        participant_patterns = [
            r'(?:posted by|written by|comment by)\s+([A-Za-z\s]+)',
            r'(?:user|member|contributor)\s+([A-Za-z\s]+)',
            r'(?:participant|tester|reviewer)\s+([A-Za-z\s]+)'
        ]
        
        for pattern in participant_patterns:
            matches = re.findall(pattern, text_content, re.IGNORECASE)
            forum_info['participants'].extend(matches)
        
        # Remove duplicates
        forum_info['emails'] = list(set(forum_info['emails']))
        forum_info['beta_mentions'] = list(set(forum_info['beta_mentions']))
        forum_info['participants'] = list(set(forum_info['participants']))
        
        return forum_info
        
    except Exception as e:
        print(f"Error extracting forum beta discussions from {forum_url}: {str(e)}")
        return {
            'emails': [],
            'discussions': [],
            'participants': [],
            'beta_mentions': []
        }