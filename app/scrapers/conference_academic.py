"""
Conference and academic scraper for discovering industry professionals
"""
import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin, urlparse
from app.utils.email_utils import decode_obfuscated_email, validate_email_address

def extract_conference_speaker_contacts(conference_url):
    """
    Extract speaker and organizer contact information from conference websites
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; ArtistPromoBot/1.0)'
        }
        
        response = requests.get(conference_url, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        conference_contacts = {
            'speakers': [],
            'organizers': [],
            'panelists': [],
            'speaker_emails': [],
            'organizer_emails': [],
            'social_links': [],
            'company_affiliations': []
        }
        
        # Look for speaker/organizer sections
        speaker_selectors = [
            '.speaker', '.presenter', '.organizer', '.staff', '.team',
            '[class*="speaker"]', '[class*="presenter"]', '[class*="organizer"]',
            '[id*="speaker"]', '[id*="presenter"]', '[id*="organizer"]'
        ]
        
        for selector in speaker_selectors:
            elements = soup.select(selector)
            for element in elements:
                text = element.get_text()
                
                # Extract names
                name_patterns = [
                    r'([A-Z][a-z]+\s+[A-Z][a-z]+)',  # Two capitalized words
                    r'([A-Z][a-z]+-[A-Z][a-z]+)',    # Hyphenated names
                    r'([A-Z][a-z]+\s+[A-Z][a-z]+\s+[A-Z][a-z]+)',  # Three capitalized words
                    r'(?:speaker|presenter|organizer|moderator):\s*([A-Za-z\s\-\'\.]+)',
                    r'(?:by\s+|with\s+|featuring\s+)([A-Za-z\s\-\'\.]+)(?:\s+from\b|\s+at\b|\s+is\b|\s+works\b)'
                ]
                
                for pattern in name_patterns:
                    matches = re.findall(pattern, text, re.IGNORECASE)
                    for match in matches:
                        cleaned_match = re.sub(r'\s+', ' ', match.strip())
                        if len(cleaned_match) > 3:  # Avoid short matches
                            if 'speaker' in pattern.lower() or 'presenter' in pattern.lower():
                                conf_contacts['speakers'].append(cleaned_match)
                            elif 'organizer' in pattern.lower() or 'staff' in pattern.lower():
                                conf_contacts['organizers'].append(cleaned_match)
                            else:
                                # Default to speaker for music industry context
                                conf_contacts['speakers'].append(cleaned_match)
        
        # Extract emails
        text_content = soup.get_text()
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        raw_emails = re.findall(email_pattern, text_content)
        
        for email in raw_emails:
            normalized_email = decode_obfuscated_email(email)
            if validate_email_address(normalized_email):
                # Try to categorize based on context
                text_lower = text_content.lower()
                if any(keyword in text_lower for keyword in ['speaker', 'presenter', 'panel']):
                    conference_contacts['speaker_emails'].append(normalized_email)
                elif any(keyword in text_lower for keyword in ['organizer', 'staff', 'team']):
                    conference_contacts['organizer_emails'].append(normalized_email)
                else:
                    # Default to speaker email for music industry context
                    conference_contacts['speaker_emails'].append(normalized_email)
        
        # Extract company affiliations
        company_patterns = [
            r'(?:at\s+|from\s+|works\s+at|represents)\s+([A-Z][a-zA-Z0-9\s\-\'\.&,]+)',
            r'([A-Z][a-zA-Z0-9\s\-\'\.&,]+)\s+(?:Inc|LLC|Ltd|Corp|Group|Records|Management|Agency|Label|Promotion)',
            r'(?:representing|affiliated\s+with)\s+([A-Z][a-zA-Z0-9\s\-\'\.&,]+)'
        ]
        
        for pattern in company_patterns:
            matches = re.findall(pattern, text_content, re.IGNORECASE)
            for match in matches:
                cleaned_match = re.sub(r'\s+', ' ', match.strip())
                if len(cleaned_match) > 3:
                    conference_contacts['company_affiliations'].append(cleaned_match)
        
        # Extract social links
        social_patterns = [
            r'(?:https?://)?(?:www\.)?linkedin\.com/in/[a-zA-Z0-9-]+',
            r'(?:https?://)?(?:www\.)?twitter\.com/[a-zA-Z0-9_]+',
            r'(?:https?://)?(?:www\.)?instagram\.com/[a-zA-Z0-9_.]+',
            r'(?:https?://)?(?:www\.)?facebook\.com/[a-zA-Z0-9_.]+',
            r'(?:https?://)?(?:www\.)?youtube\.com/@?[a-zA-Z0-9_-]+',
            r'(?:https?://)?(?:www\.)?medium\.com/@[a-zA-Z0-9]+',
            r'(?:https?://)?(?:www\.)?slideshare\.net/[a-zA-Z0-9_-]+'
        ]
        
        for pattern in social_patterns:
            matches = re.findall(pattern, text_content, re.IGNORECASE)
            conference_contacts['social_links'].extend(matches)
        
        # Remove duplicates
        conference_contacts['speakers'] = list(set(conference_contacts['speakers']))
        conference_contacts['organizers'] = list(set(conference_contacts['organizers']))
        conference_contacts['speaker_emails'] = list(set(conference_contacts['speaker_emails']))
        conference_contacts['organizer_emails'] = list(set(conference_contacts['organizer_emails']))
        conference_contacts['social_links'] = list(set(conference_contacts['social_links']))
        conference_contacts['company_affiliations'] = list(set(conference_contacts['company_affiliations']))
        
        return conference_contacts
        
    except Exception as e:
        print(f"Error extracting conference contacts from {conference_url}: {str(e)}")
        return {
            'speakers': [],
            'organizers': [],
            'panelists': [],
            'speaker_emails': [],
            'organizer_emails': [],
            'social_links': [],
            'company_affiliations': []
        }

def extract_academic_music_program_contacts(school_url):
    """
    Extract contacts from music programs at academic institutions
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; ArtistPromoBot/1.0)'
        }
        
        response = requests.get(school_url, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        academic_contacts = {
            'faculty': [],
            'staff': [],
            'students': [],
            'faculty_emails': [],
            'staff_emails': [],
            'student_emails': [],
            'research_areas': [],
            'social_links': []
        }
        
        # Look for faculty/staff pages
        faculty_selectors = [
            '.faculty', '.staff', '.personnel', '.people', '.directory',
            '[class*="faculty"]', '[class*="staff"]', '[class*="person"]',
            '[id*="faculty"]', '[id*="staff"]', '[id*="person"]'
        ]
        
        for selector in faculty_selectors:
            elements = soup.select(selector)
            for element in elements:
                text = element.get_text()
                
                # Extract names
                name_patterns = [
                    r'([A-Z][a-z]+\s+[A-Z][a-z]+)',  # Two capitalized words
                    r'([A-Z][a-z]+-[A-Z][a-z]+)',    # Hyphenated names
                    r'([A-Z][a-z]+\s+[A-Z][a-z]+\s+[A-Z][a-z]+)',  # Three capitalized words
                    r'(?:professor|instructor|lecturer|director|chair|head):\s*([A-Za-z\s\-\'\.]+)',
                    r'(?:Dr\.|Prof\.|Mr\.|Ms\.|Mrs\.)\s+([A-Za-z\s\-\'\.]+)'
                ]
                
                for pattern in name_patterns:
                    matches = re.findall(pattern, text, re.IGNORECASE)
                    for match in matches:
                        cleaned_match = re.sub(r'\s+', ' ', match.strip())
                        if len(cleaned_match) > 3:  # Avoid short matches
                            if any(title in pattern.lower() for title in ['prof', 'dr', 'lecturer', 'instructor']):
                                academic_contacts['faculty'].append(cleaned_match)
                            elif any(title in pattern.lower() for title in ['director', 'chair', 'head']):
                                academic_contacts['staff'].append(cleaned_match)
                            else:
                                academic_contacts['faculty'].append(cleaned_match)
        
        # Extract emails
        text_content = soup.get_text()
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        raw_emails = re.findall(email_pattern, text_content)
        
        for email in raw_emails:
            normalized_email = decode_obfuscated_email(email)
            if validate_email_address(normalized_email):
                # Categorize based on context
                text_lower = text_content.lower()
                if any(keyword in text_lower for keyword in ['faculty', 'professor', 'instructor', 'lecturer']):
                    academic_contacts['faculty_emails'].append(normalized_email)
                elif any(keyword in text_lower for keyword in ['staff', 'admin', 'office', 'department']):
                    academic_contacts['staff_emails'].append(normalized_email)
                else:
                    # Default to faculty for academic context
                    academic_contacts['faculty_emails'].append(normalized_email)
        
        # Extract research areas/interests
        research_patterns = [
            r'(?:research\s+area|focus|interest|specialization):\s*([A-Za-z0-9\s\-\'\.&,]+)',
            r'(?:specializes\s+in|focuses\s+on)\s+([A-Za-z0-9\s\-\'\.&,]+)',
            r'(?:expertise|knowledge\s+in)\s+([A-Za-z0-9\s\-\'\.&,]+)'
        ]
        
        for pattern in research_patterns:
            matches = re.findall(pattern, text_content, re.IGNORECASE)
            for match in matches:
                cleaned_match = re.sub(r'\s+', ' ', match.strip())
                if len(cleaned_match) > 5:
                    academic_contacts['research_areas'].append(cleaned_match)
        
        # Extract social links
        social_patterns = [
            r'(?:https?://)?(?:www\.)?linkedin\.com/in/[a-zA-Z0-9-]+',
            r'(?:https?://)?(?:www\.)?twitter\.com/[a-zA-Z0-9_]+',
            r'(?:https?://)?(?:www\.)?instagram\.com/[a-zA-Z0-9_.]+',
            r'(?:https?://)?(?:www\.)?facebook\.com/[a-zA-Z0-9_.]+',
            r'(?:https?://)?(?:www\.)?youtube\.com/@?[a-zA-Z0-9_-]+',
            r'(?:https?://)?(?:www\.)?researchgate\.net/profile/[a-zA-Z0-9_-]+',
            r'(?:https?://)?(?:www\.)?scholar\.google\.com/citations\?user=[a-zA-Z0-9_-]+'
        ]
        
        for pattern in social_patterns:
            matches = re.findall(pattern, text_content, re.IGNORECASE)
            academic_contacts['social_links'].extend(matches)
        
        # Remove duplicates
        academic_contacts['faculty'] = list(set(academic_contacts['faculty']))
        academic_contacts['staff'] = list(set(academic_contacts['staff']))
        academic_contacts['faculty_emails'] = list(set(academic_contacts['faculty_emails']))
        academic_contacts['staff_emails'] = list(set(academic_contacts['staff_emails']))
        academic_contacts['research_areas'] = list(set(academic_contacts['research_areas']))
        academic_contacts['social_links'] = list(set(academic_contacts['social_links']))
        
        return academic_contacts
        
    except Exception as e:
        print(f"Error extracting academic contacts from {school_url}: {str(e)}")
        return {
            'faculty': [],
            'staff': [],
            'students': [],
            'faculty_emails': [],
            'staff_emails': [],
            'student_emails': [],
            'research_areas': [],
            'social_links': []
        }

def extract_music_school_alumni_contacts(alumni_url):
    """
    Extract contacts from music school alumni directories
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; ArtistPromoBot/1.0)'
        }
        
        response = requests.get(alumni_url, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        alumni_contacts = {
            'alumni': [],
            'current_positions': [],
            'company_affiliations': [],
            'alumni_emails': [],
            'social_links': [],
            'graduation_years': []
        }
        
        # Look for alumni directory sections
        alumni_selectors = [
            '.alumni', '.graduate', '.former-student', '.network',
            '[class*="alumni"]', '[class*="grad"]', '[class*="network"]',
            '[id*="alumni"]', '[id*="grad"]', '[id*="network"]'
        ]
        
        for selector in alumni_selectors:
            elements = soup.select(selector)
            for element in elements:
                text = element.get_text()
                
                # Extract names
                name_patterns = [
                    r'([A-Z][a-z]+\s+[A-Z][a-z]+)',  # Two capitalized words
                    r'([A-Z][a-z]+-[A-Z][a-z]+)',    # Hyphenated names
                    r'([A-Z][a-z]+\s+[A-Z][a-z]+\s+[A-Z][a-z]+)',  # Three capitalized words
                    r'(?:alumnus|alumna|graduate|class\s+of)\s+([A-Z][a-z]+\s+[A-Z][a-z]+)',
                    r'(?:[A-Z][a-z]+\s+[A-Z][a-z]+)(?:\s*,\s*[A-Z][a-z\s]+)?(?:\s*\'\d{2,4})?'  # Name with graduation year
                ]
                
                for pattern in name_patterns:
                    matches = re.findall(pattern, text, re.IGNORECASE)
                    for match in matches:
                        cleaned_match = re.sub(r'\s+', ' ', match.strip())
                        if len(cleaned_match) > 3:  # Avoid short matches
                            alumni_contacts['alumni'].append(cleaned_match)
        
        # Extract emails
        text_content = soup.get_text()
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        raw_emails = re.findall(email_pattern, text_content)
        
        for email in raw_emails:
            normalized_email = decode_obfuscated_email(email)
            if validate_email_address(normalized_email):
                # Default to alumni email
                alumni_contacts['alumni_emails'].append(normalized_email)
        
        # Extract current positions and companies
        position_patterns = [
            r'(?:works\s+at|employed\s+by|position\s+at)\s+([A-Z][a-zA-Z0-9\s\-\'\.&,]+)',
            r'(?:[A-Z][a-z]+\s+[A-Z][a-z]+)\s+(?:at|with)\s+([A-Z][a-zA-Z0-9\s\-\'\.&,]+)',
            r'(?:currently\s+working\s+at|employed\s+at)\s+([A-Z][a-zA-Z0-9\s\-\'\.&,]+)',
            r'(?:[A-Z][a-zA-Z0-9\s\-\'\.&,]+)\s+(?:Inc|LLC|Ltd|Corp|Group|Records|Management|Agency|Label|Promotion|Studio|Company)'
        ]
        
        for pattern in position_patterns:
            matches = re.findall(pattern, text_content, re.IGNORECASE)
            for match in matches:
                cleaned_match = re.sub(r'\s+', ' ', match.strip())
                if len(cleaned_match) > 3:
                    if any(keyword in match.lower() for keyword in ['records', 'label', 'management', 'agency', 'promotion', 'studio']):
                        alumni_contacts['company_affiliations'].append(cleaned_match)
                    else:
                        alumni_contacts['current_positions'].append(cleaned_match)
        
        # Extract graduation years
        year_pattern = r'(?:class\s+of|graduated\s+in|\'|20)?(?:\d{2}|\d{4})'
        years = re.findall(year_pattern, text_content)
        alumni_contacts['graduation_years'].extend([year.strip() for year in years if len(year.strip()) >= 2])
        
        # Extract social links
        social_patterns = [
            r'(?:https?://)?(?:www\.)?linkedin\.com/in/[a-zA-Z0-9-]+',
            r'(?:https?://)?(?:www\.)?twitter\.com/[a-zA-Z0-9_]+',
            r'(?:https?://)?(?:www\.)?instagram\.com/[a-zA-Z0-9_.]+',
            r'(?:https?://)?(?:www\.)?facebook\.com/[a-zA-Z0-9_.]+',
            r'(?:https?://)?(?:www\.)?youtube\.com/@?[a-zA-Z0-9_-]+',
            r'(?:https?://)?(?:www\.)?soundcloud\.com/[a-zA-Z0-9_-]+',
            r'(?:https?://)?(?:www\.)?bandcamp\.com/[a-zA-Z0-9_-]+'
        ]
        
        for pattern in social_patterns:
            matches = re.findall(pattern, text_content, re.IGNORECASE)
            alumni_contacts['social_links'].extend(matches)
        
        # Remove duplicates
        alumni_contacts['alumni'] = list(set(alumni_contacts['alumni']))
        alumni_contacts['current_positions'] = list(set(alumni_contacts['current_positions']))
        alumni_contacts['company_affiliations'] = list(set(alumni_contacts['company_affiliations']))
        alumni_contacts['alumni_emails'] = list(set(alumni_contacts['alumni_emails']))
        alumni_contacts['social_links'] = list(set(alumni_contacts['social_links']))
        alumni_contacts['graduation_years'] = list(set(alumni_contacts['graduation_years']))
        
        return alumni_contacts
        
    except Exception as e:
        print(f"Error extracting alumni contacts from {alumni_url}: {str(e)}")
        return {
            'alumni': [],
            'current_positions': [],
            'company_affiliations': [],
            'alumni_emails': [],
            'social_links': [],
            'graduation_years': []
        }

def extract_industry_event_contacts(event_urls):
    """
    Extract contacts from industry events (conferences, workshops, panels)
    """
    all_event_contacts = {
        'events_processed': [],
        'total_speakers': [],
        'total_organizers': [],
        'total_emails': [],
        'total_companies': [],
        'total_social_links': []
    }
    
    for url in event_urls:
        try:
            if any(keyword in url.lower() for keyword in ['conference', 'summit', 'symposium', 'forum']):
                contacts = extract_conference_speaker_contacts(url)
            elif any(keyword in url.lower() for keyword in ['school', 'university', 'college', 'music', 'academy']):
                contacts = extract_academic_music_program_contacts(url)
            elif any(keyword in url.lower() for keyword in ['alumni', 'graduate', 'network']):
                contacts = extract_music_school_alumni_contacts(url)
            else:
                # Default to conference extraction for general industry events
                contacts = extract_conference_speaker_contacts(url)
            
            all_event_contacts['events_processed'].append({
                'url': url,
                'contacts': contacts
            })
            
            # Aggregate all contacts
            all_event_contacts['total_speakers'].extend(contacts.get('speakers', []))
            all_event_contacts['total_organizers'].extend(contacts.get('organizers', []))
            all_event_contacts['total_emails'].extend(contacts.get('speaker_emails', []))
            all_event_contacts['total_emails'].extend(contacts.get('organizer_emails', []))
            all_event_contacts['total_companies'].extend(contacts.get('company_affiliations', []))
            all_event_contacts['total_social_links'].extend(contacts.get('social_links', []))
            
        except Exception as e:
            print(f"Error processing event {url}: {str(e)}")
            all_event_contacts['events_processed'].append({
                'url': url,
                'error': str(e)
            })
    
    # Remove duplicates
    all_event_contacts['total_speakers'] = list(set(all_event_contacts['total_speakers']))
    all_event_contacts['total_organizers'] = list(set(all_event_contacts['total_organizers']))
    all_event_contacts['total_emails'] = list(set(all_event_contacts['total_emails']))
    all_event_contacts['total_companies'] = list(set(all_event_contacts['total_companies']))
    all_event_contacts['total_social_links'] = list(set(all_event_contacts['total_social_links']))
    
    return all_event_contacts

def find_music_industry_conferences():
    """
    Find upcoming music industry conferences that might have contact information
    """
    # This would typically involve searching for conference websites
    # For now, return a list of known music industry conferences
    known_conferences = [
        "https://www.mida.org.il/",
        "https://www.ibmra.org/",
        "https://www.musicbusinessworldwide.com/",
        "https://www.billboard.com/charts/",
        "https://www.grammy.com/",
        "https://www.ascap.com/",
        "https://www.bmi.com/",
        # Add more as needed
    ]
    
    print("Known music industry conference websites for contact extraction")
    return known_conferences

def extract_music_school_program_contacts(school_urls):
    """
    Extract contacts from music school program pages
    """
    all_school_contacts = {
        'schools_processed': [],
        'total_faculty': [],
        'total_staff': [],
        'total_emails': [],
        'total_research_areas': [],
        'total_social_links': []
    }
    
    for url in school_urls:
        try:
            contacts = extract_academic_music_program_contacts(url)
            
            all_school_contacts['schools_processed'].append({
                'url': url,
                'contacts': contacts
            })
            
            # Aggregate all contacts
            all_school_contacts['total_faculty'].extend(contacts.get('faculty', []))
            all_school_contacts['total_staff'].extend(contacts.get('staff', []))
            all_school_contacts['total_emails'].extend(contacts.get('faculty_emails', []))
            all_school_contacts['total_emails'].extend(contacts.get('staff_emails', []))
            all_school_contacts['total_research_areas'].extend(contacts.get('research_areas', []))
            all_school_contacts['total_social_links'].extend(contacts.get('social_links', []))
            
        except Exception as e:
            print(f"Error processing music school {url}: {str(e)}")
            all_school_contacts['schools_processed'].append({
                'url': url,
                'error': str(e)
            })
    
    # Remove duplicates
    all_school_contacts['total_faculty'] = list(set(all_school_contacts['total_faculty']))
    all_school_contacts['total_staff'] = list(set(all_school_contacts['total_staff']))
    all_school_contacts['total_emails'] = list(set(all_school_contacts['total_emails']))
    all_school_contacts['total_research_areas'] = list(set(all_school_contacts['total_research_areas']))
    all_school_contacts['total_social_links'] = list(set(all_school_contacts['total_social_links']))
    
    return all_school_contacts