"""
PDF metadata and content scraper for press kits and conference slides
"""
import requests
from PyPDF2 import PdfReader
from io import BytesIO
import re
from urllib.parse import urljoin
from app.utils.email_utils import decode_obfuscated_email, validate_email_address

def extract_pdf_emails(pdf_url):
    """
    Extract emails from PDF content and metadata
    """
    try:
        response = requests.get(pdf_url, timeout=30)
        response.raise_for_status()
        
        reader = PdfReader(BytesIO(response.content))
        emails = []
        
        # Extract from metadata
        if reader.metadata:
            for key, value in reader.metadata.items():
                if value:
                    # Look for emails in metadata values
                    found_emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', str(value))
                    emails.extend(found_emails)
        
        # Extract from page content
        for page in reader.pages:
            text = page.extract_text()
            found_emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
            emails.extend(found_emails)
        
        # Normalize and validate emails
        validated_emails = []
        for email in emails:
            normalized_email = decode_obfuscated_email(email)
            if validate_email_address(normalized_email):
                validated_emails.append(normalized_email)
        
        return list(set(validated_emails))  # Remove duplicates
        
    except Exception as e:
        print(f"Error extracting emails from PDF {pdf_url}: {str(e)}")
        return []

def extract_pdf_metadata(pdf_url):
    """
    Extract metadata from PDF file
    """
    try:
        response = requests.get(pdf_url, timeout=30)
        response.raise_for_status()
        
        reader = PdfReader(BytesIO(response.content))
        
        metadata = {}
        if reader.metadata:
            for key, value in reader.metadata.items():
                metadata[key] = str(value) if value else ""
        
        return metadata
        
    except Exception as e:
        print(f"Error extracting metadata from PDF {pdf_url}: {str(e)}")
        return {}

def extract_pdf_author_info(pdf_url):
    """
    Extract author and contact information from PDF
    """
    try:
        response = requests.get(pdf_url, timeout=30)
        response.raise_for_status()
        
        reader = PdfReader(BytesIO(response.content))
        author_info = []
        
        # Look for common author/creator fields in metadata
        if reader.metadata:
            metadata = reader.metadata
            for field in ['author', 'creator', 'producer', 'subject', 'title']:
                if hasattr(metadata, field) and getattr(metadata, field):
                    author_info.append(str(getattr(metadata, field)))
        
        # Look for contact information in text content
        for page in reader.pages:
            text = page.extract_text()
            # Look for common contact patterns
            contact_patterns = [
                r'contact:\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
                r'email:\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
                r'for more information contact ([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'
            ]
            
            for pattern in contact_patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                author_info.extend(matches)
        
        # Validate any emails found
        validated_info = []
        for item in author_info:
            if '@' in item:  # Likely an email
                normalized_email = decode_obfuscated_email(item)
                if validate_email_address(normalized_email):
                    validated_info.append(normalized_email)
            else:
                validated_info.append(item)
        
        return list(set(validated_info))
        
    except Exception as e:
        print(f"Error extracting author info from PDF {pdf_url}: {str(e)}")
        return []

def extract_press_kit_info(pdf_url):
    """
    Specialized function for extracting press kit information
    """
    try:
        response = requests.get(pdf_url, timeout=30)
        response.raise_for_status()
        
        reader = PdfReader(BytesIO(response.content))
        press_info = {
            'emails': [],
            'contacts': [],
            'social_links': [],
            'company_info': []
        }
        
        # Extract from all pages
        full_text = ""
        for page in reader.pages:
            full_text += page.extract_text() + " "
        
        # Extract emails
        emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', full_text)
        for email in emails:
            normalized_email = decode_obfuscated_email(email)
            if validate_email_address(normalized_email):
                press_info['emails'].append(normalized_email)
        
        # Extract social media links
        social_patterns = [
            r'(?:https?://)?(?:www\.)?instagram\.com/[a-zA-Z0-9_.]+',
            r'(?:https?://)?(?:www\.)?twitter\.com/[a-zA-Z0-9_]+',
            r'(?:https?://)?(?:www\.)?facebook\.com/[a-zA-Z0-9_.]+',
            r'(?:https?://)?(?:www\.)?linkedin\.com/[a-zA-Z0-9_.]+',
            r'(?:https?://)?(?:www\.)?youtube\.com/@?[a-zA-Z0-9_-]+'
        ]
        
        for pattern in social_patterns:
            matches = re.findall(pattern, full_text, re.IGNORECASE)
            press_info['social_links'].extend(matches)
        
        # Extract company/management info
        company_patterns = [
            r'(?:management|contact|booking):\s*([A-Za-z\s]+)',
            r'(?:managed by|represented by)\s+([A-Za-z\s]+)',
            r'(?:press contact|media contact)\s+([A-Za-z\s]+)'
        ]
        
        for pattern in company_patterns:
            matches = re.findall(pattern, full_text, re.IGNORECASE)
            press_info['company_info'].extend(matches)
        
        # Remove duplicates
        press_info['emails'] = list(set(press_info['emails']))
        press_info['social_links'] = list(set(press_info['social_links']))
        press_info['company_info'] = list(set(press_info['company_info']))
        
        return press_info
        
    except Exception as e:
        print(f"Error extracting press kit info from PDF {pdf_url}: {str(e)}")
        return {
            'emails': [],
            'contacts': [],
            'social_links': [],
            'company_info': []
        }