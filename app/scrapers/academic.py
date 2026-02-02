"""
Academic institution and alumni network scraper
"""
import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin, urlparse
from app.utils.email_utils import decode_obfuscated_email, validate_email_address

def extract_music_school_contacts(school_url):
    """
    Extract contact information from music schools and programs
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; ArtistPromoBot/1.0)'
        }
        
        response = requests.get(school_url, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        contacts = {
            'faculty': [],
            'administration': [],
            'student_orgs': [],
            'industry_partners': [],
            'emails': []
        }
        
        # Look for faculty/staff pages
        faculty_links = soup.find_all('a', href=re.compile(r'/(faculty|staff|people|directory)'))
        
        for link in faculty_links:
            faculty_url = urljoin(school_url, link.get('href'))
            faculty_contacts = extract_faculty_contacts(faculty_url)
            contacts['faculty'].extend(faculty_contacts.get('faculty', []))
            contacts['emails'].extend(faculty_contacts.get('emails', []))
        
        # Extract from current page
        text_content = soup.get_text()
        
        # Look for email patterns
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        raw_emails = re.findall(email_pattern, text_content)
        
        for email in raw_emails:
            normalized_email = decode_obfuscated_email(email)
            if validate_email_address(normalized_email):
                contacts['emails'].append(normalized_email)
        
        # Look for staff/directory pages
        directory_patterns = [
            r'faculty',
            r'staff',
            r'directory',
            r'people',
            r'administration',
            r'industry',
            r'partners',
            r'alumni'
        ]
        
        # Find links that might lead to contact pages
        all_links = soup.find_all('a', href=True)
        for link in all_links:
            href = link.get('href')
            link_text = link.get_text().lower()
            
            for pattern in directory_patterns:
                if pattern in href.lower() or pattern in link_text:
                    potential_contact_url = urljoin(school_url, href)
                    if is_valid_contact_page(potential_contact_url):
                        page_contacts = extract_contacts_from_page(potential_contact_url)
                        contacts['administration'].extend(page_contacts.get('people', []))
                        contacts['emails'].extend(page_contacts.get('emails', []))
        
        # Remove duplicates
        contacts['emails'] = list(set(contacts['emails']))
        
        return contacts
        
    except Exception as e:
        print(f"Error extracting music school contacts from {school_url}: {str(e)}")
        return {
            'faculty': [],
            'administration': [],
            'student_orgs': [],
            'industry_partners': [],
            'emails': []
        }

def extract_faculty_contacts(faculty_url):
    """
    Extract faculty contact information from faculty directory pages
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; ArtistPromoBot/1.0)'
        }
        
        response = requests.get(faculty_url, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        faculty_data = {
            'faculty': [],
            'emails': []
        }
        
        # Look for faculty profile containers
        profile_selectors = [
            '.faculty-member', '.staff-member', '.person', '.profile',
            '[class*="faculty"]', '[class*="staff"]', '[class*="person"]'
        ]
        
        for selector in profile_selectors:
            profiles = soup.select(selector)
            for profile in profiles:
                faculty_info = extract_individual_faculty_info(profile)
                if faculty_info:
                    faculty_data['faculty'].append(faculty_info)
                    if faculty_info.get('email'):
                        if validate_email_address(faculty_info['email']):
                            faculty_data['emails'].append(faculty_info['email'])
        
        # Also extract emails from page text
        text_content = soup.get_text()
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        raw_emails = re.findall(email_pattern, text_content)
        
        for email in raw_emails:
            normalized_email = decode_obfuscated_email(email)
            if validate_email_address(normalized_email):
                faculty_data['emails'].append(normalized_email)
        
        return faculty_data
        
    except Exception as e:
        print(f"Error extracting faculty contacts from {faculty_url}: {str(e)}")
        return {'faculty': [], 'emails': []}

def extract_individual_faculty_info(profile_element):
    """
    Extract individual faculty information from a profile element
    """
    try:
        # Look for common fields
        name_elem = profile_element.select_one('.name, .fullname, h3, h4, .title')
        title_elem = profile_element.select_one('.title, .position, .role')
        email_elem = profile_element.select_one('.email, a[href^="mailto:"], [data-email]')
        bio_elem = profile_element.select_one('.bio, .description, .summary')
        
        faculty_info = {}
        
        if name_elem:
            faculty_info['name'] = name_elem.get_text().strip()
        
        if title_elem:
            faculty_info['title'] = title_elem.get_text().strip()
        
        if email_elem:
            if email_elem.name == 'a' and email_elem.get('href', '').startswith('mailto:'):
                email = email_elem.get('href')[7:]  # Remove 'mailto:' prefix
            else:
                email = email_elem.get_text().strip() or email_elem.get('data-email', '')
            
            normalized_email = decode_obfuscated_email(email)
            if validate_email_address(normalized_email):
                faculty_info['email'] = normalized_email
        
        if bio_elem:
            faculty_info['bio'] = bio_elem.get_text().strip()
        
        # Extract from text content as backup
        if not faculty_info.get('name'):
            text_content = profile_element.get_text()
            # Look for name patterns (first uppercase word followed by another)
            name_match = re.search(r'([A-Z][a-z]+\s+[A-Z][a-z]+)', text_content)
            if name_match:
                faculty_info['name'] = name_match.group(1)
        
        if not faculty_info.get('email'):
            # Look for email in text content
            email_match = re.search(r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', text_content)
            if email_match:
                email = decode_obfuscated_email(email_match.group(1))
                if validate_email_address(email):
                    faculty_info['email'] = email
        
        return faculty_info if faculty_info.get('name') or faculty_info.get('email') else None
        
    except Exception as e:
        print(f"Error extracting individual faculty info: {str(e)}")
        return None

def extract_alumni_network(artist_name):
    """
    Extract contact information from alumni networks
    """
    # This would typically require searching for alumni associations
    # and may involve multiple institutions
    alumni_contacts = {
        'universities': [],
        'programs': [],
        'contacts': [],
        'emails': []
    }
    
    # Search for music-related institutions that might have the artist
    search_terms = [
        f"{artist_name} alumni",
        f"{artist_name} university",
        f"{artist_name} college",
        f"{artist_name} music school"
    ]
    
    # This would require search engine integration
    # For now, return empty with note about implementation
    print(f"Alumni network search for '{artist_name}' requires search engine integration")
    
    return alumni_contacts

def extract_industry_connections_from_academia(school_url):
    """
    Extract industry connections from academic institution pages
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; ArtistPromoBot/1.0)'
        }
        
        response = requests.get(school_url, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        industry_connections = {
            'partner_companies': [],
            'guest_speakers': [],
            'mentor_programs': [],
            'emails': []
        }
        
        # Look for industry partnership sections
        partnership_selectors = [
            '.partners', '.industry', '.collaborations', '.connections',
            '[class*="partner"]', '[class*="industry"]', '[class*="connection"]',
            '.speaker-series', '.guest-lecturer', '.mentor-program'
        ]
        
        for selector in partnership_selectors:
            sections = soup.select(selector)
            for section in sections:
                text_content = section.get_text()
                
                # Extract company names and potential contacts
                # Look for patterns like "Industry Partner: Company Name"
                company_patterns = [
                    r'(?:industry partner|collaborating with|partnered with|in partnership with)\s*:?\s*([A-Za-z\s\d\-&,]+)',
                    r'(?:guest speaker|visiting artist|industry expert)\s*:?\s*([A-Za-z\s\d\-&,]+)',
                    r'(?:mentor|advisor|consultant)\s*:?\s*([A-Za-z\s\d\-&,]+)'
                ]
                
                for pattern in company_patterns:
                    matches = re.findall(pattern, text_content, re.IGNORECASE)
                    for match in matches:
                        # Clean up the match
                        clean_match = re.sub(r'\s+', ' ', match.strip())
                        if len(clean_match) > 2:  # Avoid short matches
                            if 'speaker' in pattern or 'expert' in pattern:
                                industry_connections['guest_speakers'].append(clean_match)
                            elif 'mentor' in pattern:
                                industry_connections['mentor_programs'].append(clean_match)
                            else:
                                industry_connections['partner_companies'].append(clean_match)
        
        # Extract emails from these sections
        text_content = soup.get_text()
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        raw_emails = re.findall(email_pattern, text_content)
        
        for email in raw_emails:
            normalized_email = decode_obfuscated_email(email)
            if validate_email_address(normalized_email):
                industry_connections['emails'].append(normalized_email)
        
        # Remove duplicates
        industry_connections['partner_companies'] = list(set(industry_connections['partner_companies']))
        industry_connections['guest_speakers'] = list(set(industry_connections['guest_speakers']))
        industry_connections['mentor_programs'] = list(set(industry_connections['mentor_programs']))
        industry_connections['emails'] = list(set(industry_connections['emails']))
        
        return industry_connections
        
    except Exception as e:
        print(f"Error extracting industry connections from {school_url}: {str(e)}")
        return {
            'partner_companies': [],
            'guest_speakers': [],
            'mentor_programs': [],
            'emails': []
        }

def search_music_programs_for_contacts(artist_name):
    """
    Search music programs that might have connections to the artist
    """
    # This would involve searching for music programs at universities
    # that might have the artist in their records
    program_contacts = {
        'universities': [],
        'music_programs': [],
        'potential_contacts': [],
        'emails': []
    }
    
    # Search for music departments that might have the artist
    search_queries = [
        f"music department {artist_name}",
        f"school of music {artist_name}",
        f"conservatory {artist_name}",
        f"music program {artist_name} alumni"
    ]
    
    print(f"Music program search for '{artist_name}' requires search engine integration")
    
    return program_contacts

def extract_student_org_contacts(school_url):
    """
    Extract contacts from student organizations related to music
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; ArtistPromoBot/1.0)'
        }
        
        response = requests.get(school_url, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        org_contacts = {
            'organizations': [],
            'leaders': [],
            'emails': []
        }
        
        # Look for student organization sections
        org_selectors = [
            '.student-org', '.clubs', '.organizations', '.student-groups',
            '[class*="student"]', '[class*="club"]', '[class*="org"]',
            '.music-club', '.audio-engineering', '.recording-club'
        ]
        
        for selector in org_selectors:
            org_sections = soup.select(selector)
            for org_section in org_sections:
                # Look for organization names
                org_name_elem = org_section.select_one('h1, h2, h3, h4, .name, .title')
                if org_name_elem:
                    org_name = org_name_elem.get_text().strip()
                    if org_name not in org_contacts['organizations']:
                        org_contacts['organizations'].append(org_name)
                
                # Look for leadership information
                leader_patterns = [
                    r'(?:president|chair|leader|head|captain):\s*([A-Za-z\s\d\-&,]+)',
                    r'(?:contact person|organizer|coordinator):\s*([A-Za-z\s\d\-&,]+)',
                    r'(?:lead|director|manager):\s*([A-Za-z\s\d\-&,]+)'
                ]
                
                org_text = org_section.get_text()
                for pattern in leader_patterns:
                    matches = re.findall(pattern, org_text, re.IGNORECASE)
                    for match in matches:
                        clean_match = re.sub(r'\s+', ' ', match.strip())
                        if len(clean_match) > 2:
                            org_contacts['leaders'].append(clean_match)
        
        # Extract emails from organization sections
        all_text = soup.get_text()
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        raw_emails = re.findall(email_pattern, all_text)
        
        for email in raw_emails:
            normalized_email = decode_obfuscated_email(email)
            if validate_email_address(normalized_email):
                org_contacts['emails'].append(normalized_email)
        
        # Remove duplicates
        org_contacts['organizations'] = list(set(org_contacts['organizations']))
        org_contacts['leaders'] = list(set(org_contacts['leaders']))
        org_contacts['emails'] = list(set(org_contacts['emails']))
        
        return org_contacts
        
    except Exception as e:
        print(f"Error extracting student org contacts from {school_url}: {str(e)}")
        return {
            'organizations': [],
            'leaders': [],
            'emails': []
        }

def is_valid_contact_page(url):
    """
    Check if a URL is likely to contain contact information
    """
    contact_indicators = [
        'contact', 'directory', 'faculty', 'staff', 'people',
        'about', 'team', 'administration', 'industry', 'partners',
        'alumni', 'student', 'clubs', 'organizations'
    ]
    
    url_lower = url.lower()
    return any(indicator in url_lower for indicator in contact_indicators)

def extract_contacts_from_page(url):
    """
    Generic function to extract contacts from any page
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; ArtistPromoBot/1.0)'
        }
        
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        contact_data = {
            'people': [],
            'emails': [],
            'positions': []
        }
        
        # Extract all text
        text_content = soup.get_text()
        
        # Find emails
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        raw_emails = re.findall(email_pattern, text_content)
        
        for email in raw_emails:
            normalized_email = decode_obfuscated_email(email)
            if validate_email_address(normalized_email):
                contact_data['emails'].append(normalized_email)
        
        # Look for person names (simple heuristic)
        name_patterns = [
            r'(?:Dr\.|Mr\.|Mrs\.|Ms\.|Prof\.)\s+([A-Z][a-z]+\s+[A-Z][a-z]+)',
            r'(?:Director|Manager|Coordinator|Head|Lead)\s+([A-Z][a-z]+\s+[A-Z][a-z]+)',
            r'(?:President|Chair|CEO|Founder)\s+([A-Z][a-z]+\s+[A-Z][a-z]+)'
        ]
        
        for pattern in name_patterns:
            matches = re.findall(pattern, text_content)
            for match in matches:
                if len(match) > 2:  # Avoid short matches
                    contact_data['people'].append(match)
        
        # Look for positions/titles
        position_patterns = [
            r'(?:is\s+a\s+|works\s+as\s+a\s+|serves\s+as\s+)([A-Z][a-z\s]+?(?:\s+at\s+[A-Z][a-z\s]+)?)',
            r'(?:[A-Z][a-z\s]+?\s+(?:Manager|Director|Head|Lead|Coordinator|Specialist))'
        ]
        
        for pattern in position_patterns:
            matches = re.findall(pattern, text_content, re.IGNORECASE)
            for match in matches:
                clean_match = re.sub(r'\s+', ' ', match.strip())
                if len(clean_match) > 5:  # Avoid very short matches
                    contact_data['positions'].append(clean_match)
        
        return contact_data
        
    except Exception as e:
        print(f"Error extracting contacts from {url}: {str(e)}")
        return {
            'people': [],
            'emails': [],
            'positions': []
        }

def batch_scrape_academic_contacts(school_urls):
    """
    Batch scrape multiple academic institutions
    """
    all_contacts = {
        'schools_processed': [],
        'total_emails': [],
        'faculty_contacts': [],
        'industry_connections': [],
        'student_orgs': []
    }
    
    for url in school_urls:
        try:
            # Extract faculty contacts
            faculty_data = extract_music_school_contacts(url)
            
            # Extract industry connections
            industry_data = extract_industry_connections_from_academia(url)
            
            # Extract student org contacts
            org_data = extract_student_org_contacts(url)
            
            all_contacts['schools_processed'].append({
                'url': url,
                'faculty': faculty_data.get('faculty', []),
                'administration': faculty_data.get('administration', []),
                'emails': faculty_data.get('emails', []),
                'industry_partners': industry_data.get('partner_companies', []),
                'guest_speakers': industry_data.get('guest_speakers', []),
                'student_orgs': org_data.get('organizations', [])
            })
            
            # Aggregate all emails
            all_emails = faculty_data.get('emails', []) + industry_data.get('emails', []) + org_data.get('emails', [])
            all_contacts['total_emails'].extend(all_emails)
            
            # Aggregate faculty contacts
            all_contacts['faculty_contacts'].extend(faculty_data.get('faculty', []))
            
            # Aggregate industry connections
            all_contacts['industry_connections'].extend(industry_data.get('partner_companies', []))
            all_contacts['industry_connections'].extend(industry_data.get('guest_speakers', []))
            
            # Aggregate student orgs
            all_contacts['student_orgs'].extend(org_data.get('organizations', []))
            
        except Exception as e:
            print(f"Error processing academic institution {url}: {str(e)}")
            all_contacts['schools_processed'].append({
                'url': url,
                'error': str(e)
            })
    
    # Remove duplicates
    all_contacts['total_emails'] = list(set(all_contacts['total_emails']))

    # Remove duplicate faculty contacts while preserving dict structure
    seen_contacts = set()
    unique_faculty_contacts = []
    for contact in all_contacts['faculty_contacts']:
        # Create a hashable representation of the contact dict
        contact_tuple = tuple(sorted(contact.items())) if isinstance(contact, dict) else contact
        if contact_tuple not in seen_contacts:
            seen_contacts.add(contact_tuple)
            unique_faculty_contacts.append(contact)
    all_contacts['faculty_contacts'] = unique_faculty_contacts

    all_contacts['industry_connections'] = list(set(all_contacts['industry_connections']))
    all_contacts['student_orgs'] = list(set(all_contacts['student_orgs']))
    
    return all_contacts