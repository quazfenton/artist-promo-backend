"""
Document and file metadata scraper for discovering contacts from PDFs, DOCs, etc.
"""
import requests
import PyPDF2
import docx
from pptx import Presentation
from PIL import Image
from PIL.ExifTags import TAGS
import io
import re
from urllib.parse import urljoin, urlparse
import os
from app.utils.email_utils import decode_obfuscated_email, validate_email_address

def extract_emails_from_pdf_metadata(pdf_path_or_url):
    """
    Extract emails from PDF metadata and content
    """
    try:
        # Handle both local paths and URLs
        if pdf_path_or_url.startswith(('http://', 'https://')):
            response = requests.get(pdf_path_or_url, timeout=30)
            response.raise_for_status()
            pdf_content = io.BytesIO(response.content)
        else:
            pdf_content = pdf_path_or_url  # Local file path
        
        pdf_reader = PyPDF2.PdfReader(pdf_content)
        
        metadata_emails = []
        content_emails = []
        
        # Extract from metadata
        metadata = None
        if pdf_reader.metadata:
            metadata = pdf_reader.metadata
            for key, value in metadata.items():
                if value:
                    # Look for emails in metadata values
                    emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', str(value))
                    for email in emails:
                        normalized_email = decode_obfuscated_email(email)
                        if validate_email_address(normalized_email):
                            metadata_emails.append(normalized_email)

        # Extract from content
        for page in pdf_reader.pages:
            text = page.extract_text()
            
            # Extract emails from text
            emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
            for email in emails:
                normalized_email = decode_obfuscated_email(email)
                if validate_email_address(normalized_email):
                    content_emails.append(normalized_email)
        
        # Combine and remove duplicates
        all_emails = list(set(metadata_emails + content_emails))
        
        return {
            'metadata_emails': metadata_emails,
            'content_emails': content_emails,
            'all_emails': all_emails,
            'metadata': metadata._get_all() if metadata else {}
        }
        
    except Exception as e:
        print(f"Error extracting emails from PDF {pdf_path_or_url}: {str(e)}")
        return {
            'metadata_emails': [],
            'content_emails': [],
            'all_emails': [],
            'metadata': {}
        }

def extract_emails_from_docx_metadata(docx_path_or_url):
    """
    Extract emails from DOCX document metadata and content
    """
    try:
        # Handle both local paths and URLs
        if docx_path_or_url.startswith(('http://', 'https://')):
            response = requests.get(docx_path_or_url, timeout=30)
            response.raise_for_status()
            docx_content = io.BytesIO(response.content)
        else:
            docx_content = docx_path_or_url  # Local file path
        
        doc = docx.Document(docx_content)
        
        metadata_emails = []
        content_emails = []
        
        # Extract from core properties
        core_props = doc.core_properties
        props_to_check = [
            core_props.author, core_props.category, core_props.comments,
            core_props.identifier, core_props.keywords, core_props.subject
        ]
        
        for prop in props_to_check:
            if prop:
                emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', str(prop))
                for email in emails:
                    normalized_email = decode_obfuscated_email(email)
                    if validate_email_address(normalized_email):
                        metadata_emails.append(normalized_email)
        
        # Extract from document content
        for paragraph in doc.paragraphs:
            emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', paragraph.text)
            for email in emails:
                normalized_email = decode_obfuscated_email(email)
                if validate_email_address(normalized_email):
                    content_emails.append(normalized_email)
        
        # Also check tables and other elements
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', cell.text)
                    for email in emails:
                        normalized_email = decode_obfuscated_email(email)
                        if validate_email_address(normalized_email):
                            content_emails.append(normalized_email)
        
        # Combine and remove duplicates
        all_emails = list(set(metadata_emails + content_emails))
        
        return {
            'metadata_emails': metadata_emails,
            'content_emails': content_emails,
            'all_emails': all_emails,
            'properties': {
                'author': core_props.author,
                'title': core_props.title,
                'subject': core_props.subject,
                'category': core_props.category,
                'comments': core_props.comments,
                'keywords': core_props.keywords,
                'last_modified_by': core_props.last_modified_by,
                'revision': core_props.revision,
                'modified': core_props.modified,
                'created': core_props.created
            }
        }
        
    except Exception as e:
        print(f"Error extracting emails from DOCX {docx_path_or_url}: {str(e)}")
        return {
            'metadata_emails': [],
            'content_emails': [],
            'all_emails': [],
            'properties': {}
        }

def extract_emails_from_pptx_metadata(pptx_path_or_url):
    """
    Extract emails from PPTX presentation metadata and content
    """
    try:
        # Handle both local paths and URLs
        if pptx_path_or_url.startswith(('http://', 'https://')):
            response = requests.get(pptx_path_or_url, timeout=30)
            response.raise_for_status()
            pptx_content = io.BytesIO(response.content)
        else:
            pptx_content = pptx_path_or_url  # Local file path
        
        presentation = Presentation(pptx_content)
        
        metadata_emails = []
        content_emails = []
        
        # Extract from core properties
        core_props = presentation.core_properties
        props_to_check = [
            core_props.author, core_props.category, core_props.comments,
            core_props.identifier, core_props.keywords, core_props.subject
        ]
        
        for prop in props_to_check:
            if prop:
                emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', str(prop))
                for email in emails:
                    normalized_email = decode_obfuscated_email(email)
                    if validate_email_address(normalized_email):
                        metadata_emails.append(normalized_email)
        
        # Extract from slide content
        for slide in presentation.slides:
            for shape in slide.shapes:
                if hasattr(shape, "text"):
                    emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', shape.text)
                    for email in emails:
                        normalized_email = decode_obfuscated_email(email)
                        if validate_email_address(normalized_email):
                            content_emails.append(normalized_email)
        
        # Combine and remove duplicates
        all_emails = list(set(metadata_emails + content_emails))
        
        return {
            'metadata_emails': metadata_emails,
            'content_emails': content_emails,
            'all_emails': all_emails,
            'properties': {
                'author': core_props.author,
                'title': core_props.title,
                'subject': core_props.subject,
                'category': core_props.category,
                'comments': core_props.comments,
                'keywords': core_props.keywords,
                'last_modified_by': core_props.last_modified_by,
                'revision': core_props.revision,
                'modified': core_props.modified,
                'created': core_props.created
            }
        }
        
    except Exception as e:
        print(f"Error extracting emails from PPTX {pptx_path_or_url}: {str(e)}")
        return {
            'metadata_emails': [],
            'content_emails': [],
            'all_emails': [],
            'properties': {}
        }

def extract_emails_from_image_metadata(image_path_or_url):
    """
    Extract emails from image EXIF and metadata
    """
    try:
        # Handle both local paths and URLs
        if image_path_or_url.startswith(('http://', 'https://')):
            response = requests.get(image_path_or_url, timeout=30)
            response.raise_for_status()
            image_content = io.BytesIO(response.content)
        else:
            image_content = image_path_or_url  # Local file path
        
        image = Image.open(image_content)
        
        # Extract EXIF data
        exif_data = image._getexif()
        
        emails = []
        metadata_info = {}
        
        if exif_data:
            for tag_id, value in exif_data.items():
                tag = TAGS.get(tag_id, tag_id)
                metadata_info[tag] = value
                
                # Look for emails in EXIF data
                if isinstance(value, str):
                    found_emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', value)
                    for email in found_emails:
                        normalized_email = decode_obfuscated_email(email)
                        if validate_email_address(normalized_email):
                            emails.append(normalized_email)
        
        # Also check for IPTC and XMP metadata if available
        # This requires additional libraries like piexif or PIL with extended support
        try:
            # Try to get IPTC keywords which might contain contact info
            if hasattr(image, 'info') and 'iptc' in image.info:
                iptc_data = image.info['iptc']
                for key, value in iptc_data.items():
                    if isinstance(value, str):
                        found_emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', value)
                        for email in found_emails:
                            normalized_email = decode_obfuscated_email(email)
                            if validate_email_address(normalized_email):
                                emails.append(normalized_email)
        except:
            # IPTC might not be available in all PIL installations
            pass
        
        return {
            'emails': list(set(emails)),  # Remove duplicates
            'exif_data': metadata_info,
            'format': image.format,
            'size': image.size
        }
        
    except Exception as e:
        print(f"Error extracting emails from image {image_path_or_url}: {str(e)}")
        return {
            'emails': [],
            'exif_data': {},
            'format': None,
            'size': None
        }

def extract_contact_info_from_document(document_url):
    """
    Extract contact information from various document types
    """
    try:
        # Determine document type from URL or content
        response = requests.get(document_url, timeout=30)
        response.raise_for_status()
        
        # Get file extension
        parsed_url = urlparse(document_url)
        file_ext = os.path.splitext(parsed_url.path)[1].lower()
        
        if file_ext == '.pdf':
            return extract_emails_from_pdf_metadata(document_url)
        elif file_ext == '.docx':
            return extract_emails_from_docx_metadata(document_url)
        elif file_ext == '.pptx':
            return extract_emails_from_pptx_metadata(document_url)
        elif file_ext in ['.jpg', '.jpeg', '.png', '.tiff', '.bmp']:
            return extract_emails_from_image_metadata(document_url)
        else:
            # Try to determine from content type
            content_type = response.headers.get('content-type', '').lower()
            
            if 'pdf' in content_type:
                return extract_emails_from_pdf_metadata(document_url)
            elif 'word' in content_type or 'docx' in content_type:
                return extract_emails_from_docx_metadata(document_url)
            elif 'powerpoint' in content_type or 'pptx' in content_type:
                return extract_emails_from_pptx_metadata(document_url)
            elif 'image' in content_type:
                return extract_emails_from_image_metadata(document_url)
            else:
                return {
                    'emails': [],
                    'metadata': {},
                    'error': f'Unsupported document type: {content_type}'
                }
                
    except Exception as e:
        print(f"Error extracting contact info from document {document_url}: {str(e)}")
        return {
            'emails': [],
            'metadata': {},
            'error': str(e)
        }

def extract_press_kit_contacts(press_kit_urls):
    """
    Extract contacts from press kit documents
    """
    all_contacts = {
        'documents_processed': [],
        'total_emails': [],
        'metadata_info': [],
        'contact_patterns': []
    }
    
    for url in press_kit_urls:
        try:
            doc_contacts = extract_contact_info_from_document(url)
            
            all_contacts['documents_processed'].append({
                'url': url,
                'emails': doc_contacts.get('emails', []),
                'metadata': doc_contacts.get('metadata', {}),
                'format': doc_contacts.get('format')
            })
            
            # Add emails to total
            all_contacts['total_emails'].extend(doc_contacts.get('emails', []))
            
            # Add metadata for analysis
            all_contacts['metadata_info'].append({
                'url': url,
                'metadata': doc_contacts.get('metadata', {})
            })
            
        except Exception as e:
            print(f"Error processing press kit document {url}: {str(e)}")
            all_contacts['documents_processed'].append({
                'url': url,
                'error': str(e)
            })
    
    # Remove duplicates
    all_contacts['total_emails'] = list(set(all_contacts['total_emails']))
    
    return all_contacts

def extract_conference_slide_contacts(slide_deck_urls):
    """
    Extract contacts from conference presentation slides
    """
    all_contacts = {
        'slide_decks_processed': [],
        'speakers': [],
        'organizers': [],
        'contact_emails': [],
        'social_links': [],
        'institutional_affiliations': []
    }
    
    for url in slide_deck_urls:
        try:
            # This would typically be a PowerPoint or PDF
            contacts = extract_contact_info_from_document(url)
            
            all_contacts['slide_decks_processed'].append({
                'url': url,
                'emails': contacts.get('emails', []),
                'metadata': contacts.get('metadata', {}),
                'format': contacts.get('format')
            })
            
            # Add emails
            all_contacts['contact_emails'].extend(contacts.get('emails', []))
            
            # Extract potential speaker/organizer names from metadata
            metadata = contacts.get('metadata', {})
            for key, value in metadata.items():
                if value and isinstance(value, str):
                    # Look for names in common metadata fields
                    if key.lower() in ['author', 'creator', 'last_modified_by']:
                        # Simple name extraction - in practice you'd want NLP
                        name_matches = re.findall(r'([A-Z][a-z]+\s+[A-Z][a-z]+)', value)
                        for name in name_matches:
                            if len(name) > 3:  # Avoid short matches
                                if 'speaker' in value.lower() or 'presenter' in value.lower():
                                    all_contacts['speakers'].append(name)
                                elif 'organizer' in value.lower() or 'organizer' in value.lower():
                                    all_contacts['organizers'].append(name)
                                else:
                                    # Add to speakers as default for music industry context
                                    all_contacts['speakers'].append(name)
        
        except Exception as e:
            print(f"Error processing slide deck {url}: {str(e)}")
            all_contacts['slide_decks_processed'].append({
                'url': url,
                'error': str(e)
            })
    
    # Remove duplicates
    all_contacts['contact_emails'] = list(set(all_contacts['contact_emails']))
    all_contacts['speakers'] = list(set(all_contacts['speakers']))
    all_contacts['organizers'] = list(set(all_contacts['organizers']))
    
    return all_contacts

def extract_legal_document_contacts(legal_doc_urls):
    """
    Extract contacts from legal documents (contracts, agreements, etc.)
    """
    all_contacts = {
        'documents_processed': [],
        'parties': [],
        'representatives': [],
        'contact_emails': [],
        'law_firms': [],
        'attorneys': []
    }
    
    for url in legal_doc_urls:
        try:
            contacts = extract_contact_info_from_document(url)
            
            all_contacts['documents_processed'].append({
                'url': url,
                'emails': contacts.get('emails', []),
                'metadata': contacts.get('metadata', {}),
                'format': contacts.get('format')
            })
            
            # Add emails
            all_contacts['contact_emails'].extend(contacts.get('emails', []))
            
            # Extract legal document specific information
            content_text = ""
            # This would need to extract text from the document content
            # For now, we'll just use metadata
            
            metadata = contacts.get('metadata', {})
            for key, value in metadata.items():
                if value and isinstance(value, str):
                    # Look for legal terms that might indicate parties
                    if 'attorney' in value.lower() or 'lawyer' in value.lower() or 'counsel' in value.lower():
                        # Extract potential attorney names
                        name_matches = re.findall(r'([A-Z][a-z]+\s+[A-Z][a-z]+)', value)
                        for name in name_matches:
                            if len(name) > 3:
                                all_contacts['attorneys'].append(name)
                    
                    if 'firm' in value.lower() or 'pc' in value.lower() or 'llc' in value.lower() or 'pllc' in value.lower():
                        # Extract potential law firm names
                        all_contacts['law_firms'].append(value)
        
        except Exception as e:
            print(f"Error processing legal document {url}: {str(e)}")
            all_contacts['documents_processed'].append({
                'url': url,
                'error': str(e)
            })
    
    # Remove duplicates
    all_contacts['contact_emails'] = list(set(all_contacts['contact_emails']))
    all_contacts['parties'] = list(set(all_contacts['parties']))
    all_contacts['representatives'] = list(set(all_contacts['representatives']))
    all_contacts['law_firms'] = list(set(all_contacts['law_firms']))
    all_contacts['attorneys'] = list(set(all_contacts['attorneys']))
    
    return all_contacts

def batch_process_documents(doc_urls):
    """
    Batch process multiple documents for contact extraction
    """
    results = {
        'processed_count': 0,
        'successful_extractions': 0,
        'failed_extractions': 0,
        'total_emails_found': [],
        'document_types': {},
        'all_metadata': []
    }
    
    for url in doc_urls:
        try:
            contacts = extract_contact_info_from_document(url)
            
            results['processed_count'] += 1
            
            if contacts.get('emails'):
                results['successful_extractions'] += 1
                results['total_emails_found'].extend(contacts['emails'])
                
                # Track document type
                parsed_url = urlparse(url)
                ext = os.path.splitext(parsed_url.path)[1].lower()
                results['document_types'][ext] = results['document_types'].get(ext, 0) + 1
                
                # Store metadata
                results['all_metadata'].append({
                    'url': url,
                    'emails': contacts['emails'],
                    'metadata': contacts.get('metadata', {}),
                    'format': contacts.get('format')
                })
            else:
                results['failed_extractions'] += 1
                
        except Exception as e:
            print(f"Error processing document {url}: {str(e)}")
            results['failed_extractions'] += 1
    
    # Remove duplicates
    results['total_emails_found'] = list(set(results['total_emails_found']))
    
    return results