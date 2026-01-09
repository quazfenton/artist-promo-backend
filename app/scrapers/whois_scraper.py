"""
WHOIS and domain registration scraper
"""
import whois
import requests
import re
from urllib.parse import urlparse
from app.utils.email_utils import decode_obfuscated_email, validate_email_address

def extract_domain_registrant_emails(domain):
    """
    Extract emails from domain WHOIS data
    """
    try:
        w = whois.whois(domain)
        
        emails = []
        
        # Check various possible email fields in WHOIS data
        email_fields = [
            'email', 'emails', 'admin_email', 'tech_email', 
            'registrant_email', 'billing_email', 'abuse_email'
        ]
        
        for field in email_fields:
            if hasattr(w, field):
                value = getattr(w, field)
                if value:
                    if isinstance(value, list):
                        for item in value:
                            if isinstance(item, str):
                                emails.extend(extract_emails_from_text(item))
                            elif isinstance(item, dict) and 'email' in item:
                                emails.append(item['email'])
                    elif isinstance(value, str):
                        emails.extend(extract_emails_from_text(value))
                    elif isinstance(value, dict) and 'email' in value:
                        emails.append(value['email'])
        
        # Normalize and validate emails
        validated_emails = []
        for email in emails:
            normalized_email = decode_obfuscated_email(email)
            if validate_email_address(normalized_email):
                validated_emails.append(normalized_email)
        
        return list(set(validated_emails))  # Remove duplicates
        
    except Exception as e:
        print(f"Error getting WHOIS data for {domain}: {str(e)}")
        return []

def extract_emails_from_text(text):
    """
    Extract emails from text using regex
    """
    if not text:
        return []
    
    # Common email pattern
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    emails = re.findall(email_pattern, text)
    
    # Handle common obfuscations
    obfuscated_patterns = [
        r'([A-Za-z0-9._%+-]+)\s*(?:\[at\]|\(at\)|@|\[AT\]|\(AT\))\s*([A-Za-z0-9.-]+)\s*(?:\[dot\]|\(dot\)|\.|\[DOT\]|\(DOT\))\s*([A-Za-z]{2,})',
        r'([A-Za-z0-9._%+-]+)\s*(?: at )\s*([A-Za-z0-9.-]+)\s*(?: dot )\s*([A-Za-z]{2,})',
    ]
    
    for pattern in obfuscated_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            email = f"{match[0]}@{match[1]}.{match[2]}"
            emails.append(email)
    
    return emails

def get_domain_contact_info(domain):
    """
    Get comprehensive contact information from domain registration
    """
    try:
        w = whois.whois(domain)
        
        contact_info = {
            'registrant': {},
            'admin': {},
            'tech': {},
            'emails': [],
            'organization': None,
            'creation_date': None,
            'expiration_date': None
        }
        
        # Map WHOIS fields to contact info
        contact_mappings = {
            'registrant': ['name', 'organization', 'email', 'email_list', 'phone'],
            'admin': ['name', 'organization', 'email', 'email_list', 'phone'],
            'tech': ['name', 'organization', 'email', 'email_list', 'phone']
        }
        
        for contact_type, fields in contact_mappings.items():
            contact_data = {}
            for field in fields:
                whois_field = f"{contact_type}_{field}" if field != 'email_list' else f"{contact_type}_emails"
                
                if hasattr(w, whois_field):
                    value = getattr(w, whois_field)
                    if value:
                        contact_data[field] = value
                        if field in ['email', 'email_list'] and value:
                            if isinstance(value, list):
                                for email in value:
                                    if isinstance(email, str):
                                        normalized_email = decode_obfuscated_email(email)
                                        if validate_email_address(normalized_email):
                                            contact_info['emails'].append(normalized_email)
                            elif isinstance(value, str):
                                normalized_email = decode_obfuscated_email(value)
                                if validate_email_address(normalized_email):
                                    contact_info['emails'].append(normalized_email)
            
            contact_info[contact_type] = contact_data
        
        # Extract organization from various fields
        org_fields = ['org', 'organization', 'registrant_organization', 'admin_organization', 'tech_organization']
        for field in org_fields:
            if hasattr(w, field) and getattr(w, field):
                contact_info['organization'] = getattr(w, field)
                break
        
        # Extract dates
        date_fields = ['creation_date', 'expiration_date', 'updated_date']
        for field in date_fields:
            if hasattr(w, field) and getattr(w, field):
                contact_info[field] = getattr(w, field)
        
        # Remove duplicate emails
        contact_info['emails'] = list(set(contact_info['emails']))
        
        return contact_info
        
    except Exception as e:
        print(f"Error getting domain contact info for {domain}: {str(e)}")
        return {
            'registrant': {},
            'admin': {},
            'tech': {},
            'emails': [],
            'organization': None,
            'creation_date': None,
            'expiration_date': None
        }

def extract_domain_management_contacts(domain):
    """
    Extract management and contact information from domain WHOIS
    """
    try:
        w = whois.whois(domain)
        
        contacts = {
            'management': [],
            'technical_contacts': [],
            'administrative_contacts': [],
            'organizations': [],
            'emails': []
        }
        
        # Extract contact information from different categories
        contact_categories = {
            'management': ['registrant_name', 'registrant_org', 'registrant_email'],
            'technical': ['tech_name', 'tech_org', 'tech_email'],
            'administrative': ['admin_name', 'admin_org', 'admin_email']
        }
        
        for category, fields in contact_categories.items():
            category_contacts = []
            category_emails = []
            
            for field in fields:
                if hasattr(w, field):
                    value = getattr(w, field)
                    if value:
                        if 'email' in field and isinstance(value, (str, list)):
                            if isinstance(value, list):
                                for email in value:
                                    if isinstance(email, str):
                                        normalized_email = decode_obfuscated_email(email)
                                        if validate_email_address(normalized_email):
                                            category_emails.append(normalized_email)
                            elif isinstance(value, str):
                                normalized_email = decode_obfuscated_email(value)
                                if validate_email_address(normalized_email):
                                    category_emails.append(normalized_email)
                        elif isinstance(value, str) and len(value) > 1:
                            category_contacts.append(value)
            
            contacts[f'{category}_contacts'] = category_contacts
            contacts['emails'].extend(category_emails)
        
        # Extract organizations
        org_fields = ['org', 'organization', 'registrant_org', 'admin_org', 'tech_org']
        for field in org_fields:
            if hasattr(w, field) and getattr(w, field):
                org_value = getattr(w, field)
                if isinstance(org_value, list):
                    contacts['organizations'].extend(org_value)
                elif isinstance(org_value, str):
                    contacts['organizations'].append(org_value)
        
        # Remove duplicates
        contacts['emails'] = list(set(contacts['emails']))
        contacts['organizations'] = list(set(contacts['organizations']))
        
        # Flatten all contact names
        all_contacts = []
        for key, value in contacts.items():
            if key.endswith('_contacts') and isinstance(value, list):
                all_contacts.extend(value)
        contacts['all_contacts'] = list(set(all_contacts))
        
        return contacts
        
    except Exception as e:
        print(f"Error extracting domain management contacts for {domain}: {str(e)}")
        return {
            'management': [],
            'technical_contacts': [],
            'administrative_contacts': [],
            'organizations': [],
            'emails': [],
            'all_contacts': []
        }

def find_related_domains(primary_domain):
    """
    Find related domains that might belong to the same organization
    """
    try:
        # Get WHOIS for primary domain
        primary_whois = whois.whois(primary_domain)
        
        related_domains = {
            'by_organization': [],
            'by_emails': [],
            'by_registrar': []
        }
        
        # Look for organization name
        org_name = None
        org_fields = ['org', 'organization', 'registrant_org', 'admin_org', 'tech_org']
        for field in org_fields:
            if hasattr(primary_whois, field) and getattr(primary_whois, field):
                org_name = getattr(primary_whois, field)
                if isinstance(org_name, list):
                    org_name = org_name[0] if org_name else None
                break
        
        # Look for common registrar
        registrar = getattr(primary_whois, 'registrar', None)
        
        # Look for common emails
        common_emails = []
        email_fields = ['email', 'emails', 'admin_email', 'tech_email', 'registrant_email']
        for field in email_fields:
            if hasattr(primary_whois, field):
                value = getattr(primary_whois, field)
                if value:
                    if isinstance(value, list):
                        common_emails.extend([e for e in value if isinstance(e, str)])
                    elif isinstance(value, str):
                        common_emails.append(value)
        
        # In a real implementation, you would search for domains with:
        # 1. Same organization name
        # 2. Same email addresses
        # 3. Same registrar
        # This would require a domain search service or database
        
        # For now, return the extracted information
        return {
            'primary_domain_info': {
                'organization': org_name,
                'registrar': registrar,
                'emails': common_emails
            },
            'related_domains': {
                'by_organization': [],
                'by_emails': [],
                'by_registrar': []
            }
        }
        
    except Exception as e:
        print(f"Error finding related domains for {primary_domain}: {str(e)}")
        return {
            'primary_domain_info': {},
            'related_domains': {
                'by_organization': [],
                'by_emails': [],
                'by_registrar': []
            }
        }

def extract_pr_agency_from_domain(domain):
    """
    Attempt to identify if a domain belongs to a PR agency or management company
    """
    try:
        w = whois.whois(domain)
        
        pr_indicators = {
            'organization_keywords': [
                'public relations', 'pr agency', 'communications', 'media relations',
                'talent management', 'artist management', 'music management',
                'booking agency', 'touring', 'artist representation',
                'entertainment', 'music industry', 'artist promotion'
            ],
            'email_patterns': [
                r'pr@', r'press@', r'media@', r'booking@', r'management@',
                r'talent@', r'artist@', r'booking@', r'agent@', r'rep@'
            ]
        }
        
        indicators = {
            'is_pr_agency': False,
            'is_management': False,
            'confidence': 0,
            'keywords_found': [],
            'emails': []
        }
        
        # Check organization name for keywords
        org_fields = ['org', 'organization', 'registrant_org', 'admin_org']
        for field in org_fields:
            if hasattr(w, field):
                org_value = getattr(w, field)
                if org_value:
                    org_text = org_value if isinstance(org_value, str) else ' '.join(org_value) if isinstance(org_value, list) else ''
                    org_lower = org_text.lower()
                    
                    for keyword in pr_indicators['organization_keywords']:
                        if keyword in org_lower:
                            indicators['keywords_found'].append(keyword)
                            
                            # Increase confidence based on keyword type
                            if any(k in keyword for k in ['public relations', 'pr agency', 'media relations']):
                                indicators['is_pr_agency'] = True
                                indicators['confidence'] += 25
                            elif any(k in keyword for k in ['talent management', 'artist management', 'music management']):
                                indicators['is_management'] = True
                                indicators['confidence'] += 25
                            elif any(k in keyword for k in ['booking agency', 'artist representation']):
                                indicators['is_management'] = True
                                indicators['confidence'] += 20
        
        # Check emails for patterns
        email_fields = ['email', 'emails', 'admin_email', 'tech_email', 'registrant_email']
        for field in email_fields:
            if hasattr(w, field):
                value = getattr(w, field)
                if value:
                    email_list = value if isinstance(value, list) else [value] if isinstance(value, str) else []
                    
                    for email in email_list:
                        if isinstance(email, str):
                            normalized_email = decode_obfuscated_email(email)
                            if validate_email_address(normalized_email):
                                indicators['emails'].append(normalized_email)
                                
                                for pattern in pr_indicators['email_patterns']:
                                    if re.search(pattern, normalized_email, re.IGNORECASE):
                                        indicators['keywords_found'].append(f"email_pattern:{pattern}")
                                        indicators['confidence'] += 10
        
        # Cap confidence at 100
        indicators['confidence'] = min(100, indicators['confidence'])
        
        return indicators
        
    except Exception as e:
        print(f"Error analyzing PR agency for domain {domain}: {str(e)}")
        return {
            'is_pr_agency': False,
            'is_management': False,
            'confidence': 0,
            'keywords_found': [],
            'emails': []
        }

def batch_domain_analysis(domains):
    """
    Analyze multiple domains in batch
    """
    results = {}
    
    for domain in domains:
        try:
            results[domain] = {
                'whois_data': get_domain_contact_info(domain),
                'management_contacts': extract_domain_management_contacts(domain),
                'pr_indicators': extract_pr_agency_from_domain(domain),
                'registrant_emails': extract_domain_registrant_emails(domain)
            }
        except Exception as e:
            print(f"Error analyzing domain {domain}: {str(e)}")
            results[domain] = {
                'error': str(e),
                'whois_data': {},
                'management_contacts': {},
                'pr_indicators': {},
                'registrant_emails': []
            }
    
    return results