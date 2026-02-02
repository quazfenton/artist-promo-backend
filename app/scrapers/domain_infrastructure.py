"""
Domain and infrastructure scraper for discovering contacts through domain analysis
"""
import requests
import socket
import dns.resolver
import whois
import re
from urllib.parse import urlparse
from app.utils.email_utils import decode_obfuscated_email, validate_email_address

def extract_contacts_from_whois(domain):
    """
    Extract contact information from WHOIS data
    """
    try:
        w = whois.whois(domain)
        
        whois_contacts = {
            'registrant': {},
            'admin': {},
            'tech': {},
            'emails': [],
            'organization': None,
            'nameservers': []
        }
        
        # Extract contact information from WHOIS
        contact_fields = ['name', 'email', 'organization', 'phone']
        
        for contact_type in ['registrant', 'admin', 'tech']:
            contact_info = {}
            for field in contact_fields:
                whois_field = f"{contact_type}_{field}"
                if hasattr(w, whois_field) and getattr(w, whois_field):
                    value = getattr(w, whois_field)
                    contact_info[field] = value
                    
                    # Extract emails if found
                    if field == 'email' and value:
                        if isinstance(value, list):
                            for email in value:
                                normalized_email = decode_obfuscated_email(email)
                                if validate_email_address(normalized_email):
                                    whois_contacts['emails'].append(normalized_email)
                        elif isinstance(value, str):
                            normalized_email = decode_obfuscated_email(value)
                            if validate_email_address(normalized_email):
                                whois_contacts['emails'].append(normalized_email)

            whois_contacts[f'{contact_type}_contact'] = contact_info

        # Extract organization
        org_fields = ['org', 'organization', 'registrant_org', 'admin_org', 'tech_org']
        for field in org_fields:
            if hasattr(w, field) and getattr(w, field):
                whois_contacts['organization'] = getattr(w, field)
                break

        # Extract nameservers
        if hasattr(w, 'name_servers') and w.name_servers:
            if isinstance(w.name_servers, list):
                whois_contacts['nameservers'] = [ns.lower() for ns in w.name_servers]
            elif isinstance(w.name_servers, str):
                whois_contacts['nameservers'] = [w.name_servers.lower()]

        # Remove duplicates
        whois_contacts['emails'] = list(set(whois_contacts['emails']))
        whois_contacts['nameservers'] = list(set(whois_contacts['nameservers']))

        return whois_contacts
        
    except Exception as e:
        print(f"Error extracting WHOIS contacts for {domain}: {str(e)}")
        return {
            'registrant': {},
            'admin': {},
            'tech': {},
            'emails': [],
            'organization': None,
            'nameservers': []
        }

def extract_contacts_from_dns_records(domain):
    """
    Extract potential contact information from DNS records
    """
    dns_contacts = {
        'mx_records': [],
        'txt_records': [],
        'spf_records': [],
        'potential_emails': [],
        'domains': []
    }
    
    try:
        # Get MX records (mail servers often indicate organization structure)
        try:
            mx_records = dns.resolver.resolve(domain, 'MX')
            for record in mx_records:
                exchange = str(record.exchange).rstrip('.')
                dns_contacts['mx_records'].append(exchange)
                
                # Sometimes mail servers follow patterns like manager.domain.com
                if '.' in exchange and exchange != domain:
                    potential_subdomain = exchange.replace('.' + domain, '')
                    if '.' not in potential_subdomain:  # Single level subdomain
                        potential_email = f"{potential_subdomain}@{domain}"
                        if validate_email_address(potential_email):
                            dns_contacts['potential_emails'].append(potential_email)
        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
            pass
        
        # Get TXT records (may contain contact info, SPF, DKIM)
        try:
            txt_records = dns.resolver.resolve(domain, 'TXT')
            for record in txt_records:
                txt_value = ''.join([s.decode() for s in record.strings])
                dns_contacts['txt_records'].append(txt_value)
                
                # Look for email patterns in TXT records
                email_matches = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', txt_value)
                for email in email_matches:
                    normalized_email = decode_obfuscated_email(email)
                    if validate_email_address(normalized_email):
                        dns_contacts['potential_emails'].append(normalized_email)
                
                # Look for SPF record patterns that might indicate authorized senders
                if 'spf' in txt_value.lower() or 'v=spf' in txt_value.lower():
                    dns_contacts['spf_records'].append(txt_value)
                    
                    # Extract domains from SPF records
                    spf_domains = re.findall(r'include:([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', txt_value)
                    dns_contacts['domains'].extend(spf_domains)
                    
        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
            pass
        
        # Get A records for subdomains that might be relevant
        common_subdomains = ['mail', 'email', 'contact', 'admin', 'info', 'support', 'booking', 'press']
        for subdomain in common_subdomains:
            try:
                full_subdomain = f"{subdomain}.{domain}"
                a_records = dns.resolver.resolve(full_subdomain, 'A')
                # While we don't get emails directly from A records, 
                # the subdomain name itself might suggest contact patterns
                potential_email = f"{subdomain}@{domain}"
                if validate_email_address(potential_email):
                    dns_contacts['potential_emails'].append(potential_email)
            except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
                continue
        
        # Remove duplicates
        dns_contacts['potential_emails'] = list(set(dns_contacts['potential_emails']))
        dns_contacts['domains'] = list(set(dns_contacts['domains']))
        
        return dns_contacts
        
    except Exception as e:
        print(f"Error extracting DNS contacts for {domain}: {str(e)}")
        return {
            'mx_records': [],
            'txt_records': [],
            'spf_records': [],
            'potential_emails': [],
            'domains': []
        }

def extract_contacts_from_ssl_certificates(domain, port=443):
    """
    Extract contact information from SSL certificates
    """
    ssl_contacts = {
        'certificate_emails': [],
        'organization_info': {},
        'related_domains': [],
        'issuer': None
    }
    
    try:
        import ssl
        import OpenSSL.crypto
        
        # Get certificate
        context = ssl.create_default_context()
        with socket.create_connection((domain, port), timeout=10) as sock:
            with context.wrap_socket(sock, server_hostname=domain) as ssock:
                cert_bin = ssock.getpeercert(True)
                cert = OpenSSL.crypto.load_certificate(OpenSSL.crypto.FILETYPE_ASN1, cert_bin)
        
        # Extract subject information
        subject = cert.get_subject()
        ssl_contacts['organization_info'] = {
            'CN': subject.CN if subject.CN else None,
            'O': subject.O if subject.O else None,
            'OU': subject.OU if subject.OU else None,
            'L': subject.L if subject.L else None,
            'ST': subject.ST if subject.ST else None,
            'C': subject.C if subject.C else None
        }
        
        # Extract issuer
        issuer = cert.get_issuer()
        ssl_contacts['issuer'] = f"{issuer.O} - {issuer.CN}" if issuer.O and issuer.CN else None
        
        # Extract SANs (Subject Alternative Names) which may include related domains
        san_extension = None
        for i in range(cert.get_extension_count()):
            ext = cert.get_extension(i)
            if ext.get_short_name() == b'subjectAltName':
                san_extension = str(ext)
                break
        
        if san_extension:
            # Extract domains from SAN
            domain_matches = re.findall(r'DNS:([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', san_extension)
            ssl_contacts['related_domains'] = domain_matches
            
            # Sometimes email addresses appear in certificates
            email_matches = re.findall(r'email:([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', san_extension)
            for email in email_matches:
                normalized_email = decode_obfuscated_email(email)
                if validate_email_address(normalized_email):
                    ssl_contacts['certificate_emails'].append(normalized_email)
        
        return ssl_contacts
        
    except Exception as e:
        print(f"Error extracting SSL certificate contacts for {domain}: {str(e)}")
        return {
            'certificate_emails': [],
            'organization_info': {},
            'related_domains': [],
            'issuer': None
        }

def extract_contacts_from_domain_headers(domain_url):
    """
    Extract contact information from HTTP headers and server responses
    """
    try:
        parsed = urlparse(domain_url)
        domain = parsed.netloc if parsed.netloc else domain_url
        
        headers = {
            'User-Agent': 'Mozilla/0.0 (compatible; ArtistPromoBot/1.0)'
        }
        
        response = requests.get(f"https://{domain}" if not domain_url.startswith(('http://', 'https://')) else domain_url, 
                               headers=headers, timeout=15, allow_redirects=True)
        
        header_contacts = {
            'server_info': response.headers.get('Server'),
            'x_powered_by': response.headers.get('X-Powered-By'),
            'x_generator': response.headers.get('X-Generator'),
            'x_contact_headers': [],
            'potential_emails': []
        }
        
        # Look for contact-related headers
        contact_header_patterns = [
            'x-contact', 'x-manager', 'x-admin', 'x-owner', 'x-webmaster',
            'x-technical-contact', 'x-billing-contact', 'x-abuse-contact'
        ]
        
        for header_name, header_value in response.headers.items():
            if any(pattern in header_name.lower() for pattern in contact_header_patterns):
                header_contacts['x_contact_headers'].append({
                    'header': header_name,
                    'value': header_value
                })
                
                # Look for emails in header values
                email_matches = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', header_value)
                for email in email_matches:
                    normalized_email = decode_obfuscated_email(email)
                    if validate_email_address(normalized_email):
                        header_contacts['potential_emails'].append(normalized_email)
        
        # Check for redirects that might reveal management domains
        if response.history:
            for redirect in response.history:
                redirect_domain = urlparse(redirect.url).netloc
                if redirect_domain != domain:
                    header_contacts['potential_emails'].append(f"info@{redirect_domain}")
        
        # Remove duplicates
        header_contacts['potential_emails'] = list(set(header_contacts['potential_emails']))
        
        return header_contacts
        
    except Exception as e:
        print(f"Error extracting header contacts for {domain_url}: {str(e)}")
        return {
            'server_info': None,
            'x_powered_by': None,
            'x_generator': None,
            'x_contact_headers': [],
            'potential_emails': []
        }

def discover_management_domains_from_infrastructure(domain):
    """
    Discover related management domains from infrastructure patterns
    """
    try:
        # Get the IP address
        ip_address = socket.gethostbyname(domain)
        
        # Get reverse DNS
        try:
            reverse_dns = socket.gethostbyaddr(ip_address)[0]
        except:
            reverse_dns = None
        
        # Check for common management patterns in the same IP space
        # This is a simplified version - in practice you'd want to check CIDR ranges
        management_indicators = [
            'mgmt', 'management', 'booking', 'press', 'publicity', 'promo',
            'artist', 'talent', 'booking', 'agency', 'represent'
        ]
        
        infrastructure_info = {
            'ip_address': ip_address,
            'reverse_dns': reverse_dns,
            'related_subdomains': [],
            'potential_management_domains': []
        }
        
        # Check common management subdomains
        for indicator in management_indicators:
            try:
                test_domain = f"{indicator}.{domain}"
                socket.gethostbyname(test_domain)
                infrastructure_info['related_subdomains'].append(test_domain)
                
                # Potential contact email
                potential_emails = [f"{indicator}@{domain}", f"info@{test_domain}"]
                for email in potential_emails:
                    if validate_email_address(email):
                        infrastructure_info['potential_management_domains'].append(email)
                        
            except socket.gaierror:
                continue  # Subdomain doesn't exist
        
        return infrastructure_info
        
    except Exception as e:
        print(f"Error discovering management domains for {domain}: {str(e)}")
        return {
            'ip_address': None,
            'reverse_dns': None,
            'related_subdomains': [],
            'potential_management_domains': []
        }

def comprehensive_domain_analysis(domain):
    """
    Perform comprehensive domain analysis for contact discovery
    """
    analysis_results = {
        'domain': domain,
        'whois_contacts': {},
        'dns_contacts': {},
        'ssl_contacts': {},
        'header_contacts': {},
        'infrastructure_contacts': {},
        'all_emails': [],
        'all_domains': [],
        'confidence_scores': {}
    }
    
    # Run all domain analysis modules
    analysis_results['whois_contacts'] = extract_contacts_from_whois(domain)
    analysis_results['dns_contacts'] = extract_contacts_from_dns_records(domain)
    analysis_results['ssl_contacts'] = extract_contacts_from_ssl_certificates(domain)
    analysis_results['header_contacts'] = extract_contacts_from_domain_headers(f"https://{domain}")
    analysis_results['infrastructure_contacts'] = discover_management_domains_from_infrastructure(domain)
    
    # Aggregate all emails
    all_emails = []
    all_emails.extend(analysis_results['whois_contacts'].get('emails', []))
    all_emails.extend(analysis_results['dns_contacts'].get('potential_emails', []))
    all_emails.extend(analysis_results['ssl_contacts'].get('certificate_emails', []))
    all_emails.extend(analysis_results['header_contacts'].get('potential_emails', []))
    
    # Aggregate all related domains
    all_domains = []
    all_domains.extend(analysis_results['dns_contacts'].get('domains', []))
    all_domains.extend(analysis_results['ssl_contacts'].get('related_domains', []))
    all_domains.extend(analysis_results['infrastructure_contacts'].get('related_subdomains', []))
    
    # Remove duplicates
    analysis_results['all_emails'] = list(set(all_emails))
    analysis_results['all_domains'] = list(set(all_domains))
    
    # Calculate confidence scores based on source reliability
    confidence_sources = {
        'whois': 0.7,  # WHOIS data is often legitimate but can be privacy-protected
        'dns_txt': 0.6,  # DNS records are harder to fake
        'ssl_cert': 0.8,  # SSL certs require domain control
        'headers': 0.4,  # Headers can be easily manipulated
        'infrastructure': 0.5  # Infrastructure patterns are suggestive
    }
    
    # Assign confidence scores to emails based on source
    email_confidence = {}
    for email in analysis_results['all_emails']:
        email_confidence[email] = 0.3  # Base confidence
        
        # Boost based on source
        if email in analysis_results['whois_contacts'].get('emails', []):
            email_confidence[email] = max(email_confidence[email], confidence_sources['whois'])
        
        if email in analysis_results['dns_contacts'].get('potential_emails', []):
            email_confidence[email] = max(email_confidence[email], confidence_sources['dns_txt'])
        
        if email in analysis_results['ssl_contacts'].get('certificate_emails', []):
            email_confidence[email] = max(email_confidence[email], confidence_sources['ssl_cert'])
    
    analysis_results['confidence_scores'] = email_confidence
    
    return analysis_results

def batch_domain_analysis(domains):
    """
    Perform batch domain analysis for multiple domains
    """
    all_results = []
    
    for domain in domains:
        try:
            result = comprehensive_domain_analysis(domain)
            all_results.append(result)
        except Exception as e:
            print(f"Error analyzing domain {domain}: {str(e)}")
            all_results.append({
                'domain': domain,
                'error': str(e),
                'whois_contacts': {},
                'dns_contacts': {},
                'ssl_contacts': {},
                'header_contacts': {},
                'infrastructure_contacts': {},
                'all_emails': [],
                'all_domains': [],
                'confidence_scores': {}
            })
    
    return all_results