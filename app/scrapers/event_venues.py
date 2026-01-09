"""
Event and venue scraper for discovering booking agents and venue contacts
"""
import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin, urlparse
from app.utils.email_utils import decode_obfuscated_email, validate_email_address

def extract_venue_booking_contacts(venue_url):
    """
    Extract booking and contact information from venue websites
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; ArtistPromoBot/1.0)'
        }
        
        response = requests.get(venue_url, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        venue_contacts = {
            'booking_emails': [],
            'general_emails': [],
            'booking_agents': [],
            'venue_management': [],
            'social_links': [],
            'booking_info': {}
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
        
        # Categorize emails based on context
        text_lower = text_content.lower()
        for email in validated_emails:
            if any(keyword in text_lower for keyword in ['book', 'booking', 'bookings', 'ticket', 'reservation']):
                venue_contacts['booking_emails'].append(email)
            elif any(keyword in text_lower for keyword in ['contact', 'info', 'general', 'hello', 'admin']):
                venue_contacts['general_emails'].append(email)
            else:
                # Default to general if no specific category found
                venue_contacts['general_emails'].append(email)
        
        # Extract booking agent names
        name_patterns = [
            r'(?:booking contact|bookings?|contact person|agent|representative):\s*([A-Za-z\s\-\'\.]+)',
            r'(?:contact|reach out to)\s+([A-Za-z\s\-\'\.]+)(?:\s+at\b|\s+for\b)',
            r'(?:booking\s+inquiries?\s+to|contact\s+for\s+booking)\s+([A-Za-z\s\-\'\.]+)',
            r'(?:bookings?|booking\s+agent)\s+([A-Za-z\s\-\'\.]+)',
            r'(?:venue\s+manager|booking\s+manager)\s+([A-Za-z\s\-\'\.]+)',
            r'(?:general\s+manager|operations\s+manager)\s+([A-Za-z\s\-\'\.]+)'
        ]
        
        for pattern in name_patterns:
            matches = re.findall(pattern, text_content, re.IGNORECASE)
            for match in matches:
                # Clean up the match
                cleaned_match = re.sub(r'\s+', ' ', match.strip())
                if len(cleaned_match) > 2:  # Avoid single letters
                    # Determine type based on pattern
                    if 'booking' in pattern.lower() or 'bookings' in pattern.lower():
                        venue_contacts['booking_agents'].append(cleaned_match)
                    else:
                        venue_contacts['venue_management'].append(cleaned_match)
        
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
            venue_contacts['social_links'].extend(matches)
        
        # Extract booking info from common elements
        booking_selectors = [
            '.booking', '.contact', '.info', '.details', '[class*="book"]', 
            '[class*="contact"]', '[id*="book"]', '[id*="contact"]'
        ]
        
        for selector in booking_selectors:
            elements = soup.select(selector)
            for element in elements:
                element_text = element.get_text().lower()
                if any(keyword in element_text for keyword in ['book', 'booking', 'contact', 'email']):
                    # Extract any relevant info from this element
                    links = element.find_all('a', href=True)
                    for link in links:
                        href = link['href']
                        if href.startswith('mailto:'):
                            email = href[7:]  # Remove 'mailto:' prefix
                            normalized_email = decode_obfuscated_email(email)
                            if validate_email_address(normalized_email):
                                if 'booking' in element_text or 'book' in element_text:
                                    venue_contacts['booking_emails'].append(normalized_email)
                                else:
                                    venue_contacts['general_emails'].append(normalized_email)
        
        # Remove duplicates
        venue_contacts['booking_emails'] = list(set(venue_contacts['booking_emails']))
        venue_contacts['general_emails'] = list(set(venue_contacts['general_emails']))
        venue_contacts['booking_agents'] = list(set(venue_contacts['booking_agents']))
        venue_contacts['venue_management'] = list(set(venue_contacts['venue_management']))
        venue_contacts['social_links'] = list(set(venue_contacts['social_links']))
        
        return venue_contacts
        
    except Exception as e:
        print(f"Error extracting venue contacts from {venue_url}: {str(e)}")
        return {
            'booking_emails': [],
            'general_emails': [],
            'booking_agents': [],
            'venue_management': [],
            'social_links': [],
            'booking_info': {}
        }

def extract_festival_lineup_contacts(festival_url):
    """
    Extract contacts from festival lineup pages and booking information
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; ArtistPromoBot/1.0)'
        }
        
        response = requests.get(festival_url, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        festival_contacts = {
            'booking_agents': [],
            'festival_staff': [],
            'artist_management': [],
            'booking_emails': [],
            'press_emails': [],
            'social_links': [],
            'lineup_artists': []
        }
        
        # Extract lineup information
        lineup_selectors = [
            '.lineup', '.artist', '.performer', '.schedule', 
            '[class*="lineup"]', '[class*="artist"]', '[class*="performer"]'
        ]
        
        for selector in lineup_selectors:
            elements = soup.select(selector)
            for element in elements:
                text = element.get_text()
                
                # Look for artist names in the lineup
                # This is a simplified approach - in practice you'd want more sophisticated name recognition
                name_patterns = [
                    r'([A-Z][a-z]+\s+[A-Z][a-z]+)',  # Two capitalized words
                    r'([A-Z][a-z]+-[A-Z][a-z]+)',    # Hyphenated names
                    r'([A-Z][a-z]+\s+[A-Z][a-z]+\s+[A-Z][a-z]+)'  # Three capitalized words
                ]
                
                for pattern in name_patterns:
                    matches = re.findall(pattern, text)
                    for match in matches:
                        if len(match) > 3:  # Avoid short matches
                            festival_contacts['lineup_artists'].append(match)
        
        # Extract contact information
        text_content = soup.get_text()
        
        # Extract emails
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        raw_emails = re.findall(email_pattern, text_content)
        
        for email in raw_emails:
            normalized_email = decode_obfuscated_email(email)
            if validate_email_address(normalized_email):
                if any(keyword in text_content.lower() for keyword in ['booking', 'book', 'agent', 'represent']):
                    festival_contacts['booking_emails'].append(normalized_email)
                elif any(keyword in text_content.lower() for keyword in ['press', 'media', 'publicity']):
                    festival_contacts['press_emails'].append(normalized_email)
                else:
                    festival_contacts['booking_emails'].append(normalized_email)  # Default to booking
        
        # Extract names of staff/agents
        staff_patterns = [
            r'(?:booking\s+agent|talent\s+buyer|programming\s+director|festival\s+director|booker):\s*([A-Za-z\s\-\'\.]+)',
            r'(?:contact\s+for\s+bookings|booking\s+inquiries\s+to):\s*([A-Za-z\s\-\'\.]+)',
            r'(?:festival\s+staff|team\s+member):\s*([A-Za-z\s\-\'\.]+)',
            r'(?:head\s+of\s+programming|programming\s+head):\s*([A-Za-z\s\-\'\.]+)',
            r'(?:talent\s+coordinator|artist\s+liaison):\s*([A-Za-z\s\-\'\.]+)'
        ]
        
        for pattern in staff_patterns:
            matches = re.findall(pattern, text_content, re.IGNORECASE)
            for match in matches:
                cleaned_match = re.sub(r'\s+', ' ', match.strip())
                if len(cleaned_match) > 2:
                    if 'booking' in pattern.lower() or 'booker' in pattern.lower() or 'talent' in pattern.lower():
                        festival_contacts['booking_agents'].append(cleaned_match)
                    elif 'festival' in pattern.lower() or 'director' in pattern.lower():
                        festival_contacts['festival_staff'].append(cleaned_match)
                    else:
                        festival_contacts['festival_staff'].append(cleaned_match)
        
        # Extract social links
        social_patterns = [
            r'(?:https?://)?(?:www\.)?instagram\.com/[a-zA-Z0-9_.]+',
            r'(?:https?://)?(?:www\.)?twitter\.com/[a-zA-Z0-9_]+',
            r'(?:https?://)?(?:www\.)?facebook\.com/[a-zA-Z0-9_.]+',
            r'(?:https?://)?(?:www\.)?linkedin\.com/[a-zA-Z0-9_.]+',
            r'(?:https?://)?(?:www\.)?youtube\.com/@?[a-zA-Z0-9_-]+',
            r'(?:https?://)?(?:www\.)?soundcloud\.com/[a-zA-Z0-9_-]+',
            r'(?:https?://)?(?:www\.)?bandcamp\.com/[a-zA-Z0-9_-]+'
        ]
        
        for pattern in social_patterns:
            matches = re.findall(pattern, text_content, re.IGNORECASE)
            festival_contacts['social_links'].extend(matches)
        
        # Remove duplicates
        festival_contacts['booking_agents'] = list(set(festival_contacts['booking_agents']))
        festival_contacts['festival_staff'] = list(set(festival_contacts['festival_staff']))
        festival_contacts['artist_management'] = list(set(festival_contacts['artist_management']))
        festival_contacts['booking_emails'] = list(set(festival_contacts['booking_emails']))
        festival_contacts['press_emails'] = list(set(festival_contacts['press_emails']))
        festival_contacts['social_links'] = list(set(festival_contacts['social_links']))
        festival_contacts['lineup_artists'] = list(set(festival_contacts['lineup_artists']))
        
        return festival_contacts
        
    except Exception as e:
        print(f"Error extracting festival contacts from {festival_url}: {str(e)}")
        return {
            'booking_agents': [],
            'festival_staff': [],
            'artist_management': [],
            'booking_emails': [],
            'press_emails': [],
            'social_links': [],
            'lineup_artists': []
        }

def extract_promoter_contacts(promoter_url):
    """
    Extract contacts from music promoter websites
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; ArtistPromoBot/1.0)'
        }
        
        response = requests.get(promoter_url, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        promoter_contacts = {
            'booking_agents': [],
            'promoter_staff': [],
            'artist_management': [],
            'booking_emails': [],
            'general_emails': [],
            'social_links': [],
            'roster_artists': [],
            'past_events': []
        }
        
        # Look for contact pages or booking sections
        contact_selectors = [
            '.contact', '.booking', '.inquiries', '.get-in-touch',
            '[class*="contact"]', '[class*="book"]', '[id*="contact"]', '[id*="book"]'
        ]
        
        for selector in contact_selectors:
            elements = soup.select(selector)
            for element in elements:
                element_text = element.get_text()
                
                # Extract emails from contact sections
                email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
                emails = re.findall(email_pattern, element_text)
                
                for email in emails:
                    normalized_email = decode_obfuscated_email(email)
                    if validate_email_address(normalized_email):
                        if any(keyword in element_text.lower() for keyword in ['book', 'booking', 'agent', 'talent']):
                            promoter_contacts['booking_emails'].append(normalized_email)
                        else:
                            promoter_contacts['general_emails'].append(normalized_email)
                
                # Extract names
                name_patterns = [
                    r'(?:booking\s+agent|talent\s+buyer|promoter|agent|representative):\s*([A-Za-z\s\-\'\.]+)',
                    r'(?:contact\s+for\s+bookings|booking\s+inquiries\s+to):\s*([A-Za-z\s\-\'\.]+)',
                    r'(?:our\s+team|meet\s+the\s+team).*?([A-Za-z\s\-\'\.]+)',
                    r'(?:promoter|booker|agent)\s+([A-Za-z\s\-\'\.]+)'
                ]
                
                for pattern in name_patterns:
                    matches = re.findall(pattern, element_text, re.IGNORECASE)
                    for match in matches:
                        cleaned_match = re.sub(r'\s+', ' ', match.strip())
                        if len(cleaned_match) > 2:
                            if 'booking' in pattern.lower() or 'agent' in pattern.lower() or 'talent' in pattern.lower():
                                promoter_contacts['booking_agents'].append(cleaned_match)
                            else:
                                promoter_contacts['promoter_staff'].append(cleaned_match)
        
        # Extract from main page text
        text_content = soup.get_text()
        
        # Extract emails from entire page
        all_emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text_content)
        for email in all_emails:
            normalized_email = decode_obfuscated_email(email)
            if validate_email_address(normalized_email):
                if email not in promoter_contacts['booking_emails'] and email not in promoter_contacts['general_emails']:
                    if any(keyword in text_content.lower() for keyword in ['book', 'booking', 'agent', 'talent']):
                        promoter_contacts['booking_emails'].append(normalized_email)
                    else:
                        promoter_contacts['general_emails'].append(normalized_email)
        
        # Extract artist roster
        roster_selectors = [
            '.roster', '.artists', '.acts', '.lineup', '.talent',
            '[class*="roster"]', '[class*="artist"]', '[class*="act"]', '[class*="talent"]'
        ]
        
        for selector in roster_selectors:
            elements = soup.select(selector)
            for element in elements:
                text = element.get_text()
                # Look for artist names (simplified pattern)
                name_patterns = [
                    r'([A-Z][a-z]+\s+[A-Z][a-z]+)',  # Two capitalized words
                    r'([A-Z][a-z]+-[A-Z][a-z]+)',    # Hyphenated names
                    r'([A-Z][a-z]+\s+[A-Z][a-z]+\s+[A-Z][a-z]+)'  # Three capitalized words
                ]
                
                for pattern in name_patterns:
                    matches = re.findall(pattern, text)
                    for match in matches:
                        if len(match) > 3:  # Avoid short matches
                            promoter_contacts['roster_artists'].append(match)
        
        # Extract social media links
        social_patterns = [
            r'(?:https?://)?(?:www\.)?instagram\.com/[a-zA-Z0-9_.]+',
            r'(?:https?://)?(?:www\.)?twitter\.com/[a-zA-Z0-9_]+',
            r'(?:https?://)?(?:www\.)?facebook\.com/[a-zA-Z0-9_.]+',
            r'(?:https?://)?(?:www\.)?linkedin\.com/[a-zA-Z0-9_.]+',
            r'(?:https?://)?(?:www\.)?youtube\.com/@?[a-zA-Z0-9_-]+',
            r'(?:https?://)?(?:www\.)?soundcloud\.com/[a-zA-Z0-9_-]+',
            r'(?:https?://)?(?:www\.)?bandcamp\.com/[a-zA-Z0-9_-]+',
            r'(?:https?://)?(?:www\.)?eventbrite\.com/[a-zA-Z0-9/-_]+'
        ]
        
        for pattern in social_patterns:
            matches = re.findall(pattern, text_content, re.IGNORECASE)
            promoter_contacts['social_links'].extend(matches)
        
        # Remove duplicates
        promoter_contacts['booking_agents'] = list(set(promoter_contacts['booking_agents']))
        promoter_contacts['promoter_staff'] = list(set(promoter_contacts['promoter_staff']))
        promoter_contacts['artist_management'] = list(set(promoter_contacts['artist_management']))
        promoter_contacts['booking_emails'] = list(set(promoter_contacts['booking_emails']))
        promoter_contacts['general_emails'] = list(set(promoter_contacts['general_emails']))
        promoter_contacts['social_links'] = list(set(promoter_contacts['social_links']))
        promoter_contacts['roster_artists'] = list(set(promoter_contacts['roster_artists']))
        
        return promoter_contacts
        
    except Exception as e:
        print(f"Error extracting promoter contacts from {promoter_url}: {str(e)}")
        return {
            'booking_agents': [],
            'promoter_staff': [],
            'artist_management': [],
            'booking_emails': [],
            'general_emails': [],
            'social_links': [],
            'roster_artists': [],
            'past_events': []
        }

def extract_event_series_contacts(event_series_urls):
    """
    Extract contacts from recurring event series websites
    """
    all_contacts = {
        'events_processed': [],
        'total_booking_agents': [],
        'total_venue_contacts': [],
        'total_emails': [],
        'total_artists': []
    }
    
    for url in event_series_urls:
        try:
            # Determine type of event and use appropriate extractor
            if any(keyword in url.lower() for keyword in ['festival']):
                contacts = extract_festival_lineup_contacts(url)
            elif any(keyword in url.lower() for keyword in ['venue', 'club', 'bar']):
                contacts = extract_venue_booking_contacts(url)
            else:
                # Default to promoter extraction for general event sites
                contacts = extract_promoter_contacts(url)
            
            all_contacts['events_processed'].append({
                'url': url,
                'contacts': contacts
            })
            
            # Aggregate all contacts
            all_contacts['total_booking_agents'].extend(contacts.get('booking_agents', []))
            all_contacts['total_venue_contacts'].extend(contacts.get('venue_management', []))
            all_contacts['total_emails'].extend(contacts.get('booking_emails', []))
            all_contacts['total_emails'].extend(contacts.get('general_emails', []))
            all_contacts['total_artists'].extend(contacts.get('lineup_artists', []))
            all_contacts['total_artists'].extend(contacts.get('roster_artists', []))
            
        except Exception as e:
            print(f"Error processing event series {url}: {str(e)}")
            all_contacts['events_processed'].append({
                'url': url,
                'error': str(e)
            })
    
    # Remove duplicates
    all_contacts['total_booking_agents'] = list(set(all_contacts['total_booking_agents']))
    all_contacts['total_venue_contacts'] = list(set(all_contacts['total_venue_contacts']))
    all_contacts['total_emails'] = list(set(all_contacts['total_emails']))
    all_contacts['total_artists'] = list(set(all_contacts['total_artists']))
    
    return all_contacts

def find_booking_agency_contacts(agency_urls):
    """
    Extract contacts from booking agency websites
    """
    all_agency_contacts = {
        'agencies_processed': [],
        'booking_agents': [],
        'agency_staff': [],
        'contact_emails': [],
        'represented_artists': [],
        'social_links': []
    }
    
    for url in agency_urls:
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (compatible; ArtistPromoBot/1.0)'
            }
            
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            agency_contacts = {
                'booking_agents': [],
                'agency_staff': [],
                'contact_emails': [],
                'represented_artists': [],
                'social_links': []
            }
            
            # Look for agent/representative pages
            agent_selectors = [
                '.agent', '.representative', '.team', '.staff', '.booker',
                '[class*="agent"]', '[class*="rep"]', '[class*="book"]', '[class*="team"]'
            ]
            
            for selector in agent_selectors:
                elements = soup.select(selector)
                for element in elements:
                    text = element.get_text()
                    
                    # Extract names
                    name_patterns = [
                        r'([A-Z][a-z]+\s+[A-Z][a-z]+)',  # Two capitalized words
                        r'(?:agent|representative|booker|manager):\s*([A-Z][a-z]+\s+[A-Z][a-z]+)',
                        r'(?:contact|reach out to)\s+([A-Z][a-z]+\s+[A-Z][a-z]+)'
                    ]
                    
                    for pattern in name_patterns:
                        matches = re.findall(pattern, text)
                        for match in matches:
                            cleaned_match = re.sub(r'\s+', ' ', match.strip())
                            if len(cleaned_match) > 3:
                                agency_contacts['booking_agents'].append(cleaned_match)
            
            # Extract emails
            text_content = soup.get_text()
            emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text_content)
            
            for email in emails:
                normalized_email = decode_obfuscated_email(email)
                if validate_email_address(normalized_email):
                    agency_contacts['contact_emails'].append(normalized_email)
            
            # Extract artist roster
            roster_selectors = [
                '.roster', '.artists', '.acts', '.talent', '.clients',
                '[class*="roster"]', '[class*="artist"]', '[class*="act"]', '[class*="talent"]', '[class*="client"]'
            ]
            
            for selector in roster_selectors:
                elements = soup.select(selector)
                for element in elements:
                    text = element.get_text()
                    # Look for artist names
                    name_patterns = [
                        r'([A-Z][a-z]+\s+[A-Z][a-z]+)',  # Two capitalized words
                        r'([A-Z][a-z]+-[A-Z][a-z]+)',    # Hyphenated names
                        r'([A-Z][a-z]+\s+[A-Z][a-z]+\s+[A-Z][a-z]+)'  # Three capitalized words
                    ]
                    
                    for pattern in name_patterns:
                        matches = re.findall(pattern, text)
                        for match in matches:
                            if len(match) > 3:  # Avoid short matches
                                agency_contacts['represented_artists'].append(match)
            
            # Extract social links
            social_patterns = [
                r'(?:https?://)?(?:www\.)?instagram\.com/[a-zA-Z0-9_.]+',
                r'(?:https?://)?(?:www\.)?twitter\.com/[a-zA-Z0-9_]+',
                r'(?:https?://)?(?:www\.)?facebook\.com/[a-zA-Z0-9_.]+',
                r'(?:https?://)?(?:www\.)?linkedin\.com/[a-zA-Z0-9_.]+',
                r'(?:https?://)?(?:www\.)?youtube\.com/@?[a-zA-Z0-9_-]+',
                r'(?:https?://)?(?:www\.)?soundcloud\.com/[a-zA-Z0-9_-]+',
                r'(?:https?://)?(?:www\.)?bandcamp\.com/[a-zA-Z0-9_-]+'
            ]
            
            for pattern in social_patterns:
                matches = re.findall(pattern, text_content, re.IGNORECASE)
                agency_contacts['social_links'].extend(matches)
            
            # Add to overall results
            all_agency_contacts['agencies_processed'].append({
                'url': url,
                'contacts': agency_contacts
            })
            
            all_agency_contacts['booking_agents'].extend(agency_contacts['booking_agents'])
            all_agency_contacts['agency_staff'].extend(agency_contacts['agency_staff'])
            all_agency_contacts['contact_emails'].extend(agency_contacts['contact_emails'])
            all_agency_contacts['represented_artists'].extend(agency_contacts['represented_artists'])
            all_agency_contacts['social_links'].extend(agency_contacts['social_links'])
            
        except Exception as e:
            print(f"Error processing booking agency {url}: {str(e)}")
            all_agency_contacts['agencies_processed'].append({
                'url': url,
                'error': str(e)
            })
    
    # Remove duplicates
    all_agency_contacts['booking_agents'] = list(set(all_agency_contacts['booking_agents']))
    all_agency_contacts['agency_staff'] = list(set(all_agency_contacts['agency_staff']))
    all_agency_contacts['contact_emails'] = list(set(all_agency_contacts['contact_emails']))
    all_agency_contacts['represented_artists'] = list(set(all_agency_contacts['represented_artists']))
    all_agency_contacts['social_links'] = list(set(all_agency_contacts['social_links']))
    
    return all_agency_contacts