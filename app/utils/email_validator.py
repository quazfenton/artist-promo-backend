"""
Email validation and enrichment utilities
"""
import re
import dns.resolver
from typing import Optional, Dict
import requests
from loguru import logger
from email_validator import validate_email as ev_validate, EmailNotValidError
import os


class EmailValidator:
    """Validate and enrich email addresses"""
    
    def __init__(self):
        self.hunter_api_key = os.getenv("HUNTER_API_KEY")
        self.neverbounce_api_key = os.getenv("NEVERBOUNCE_API_KEY")
    
    def basic_validate(self, email: str) -> bool:
        """Basic regex validation"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    def advanced_validate(self, email: str) -> Dict:
        """
        Advanced validation with DNS check
        Returns dict with validation results
        """
        result = {
            "email": email,
            "valid": False,
            "deliverable": False,
            "mx_records": False,
            "disposable": False,
            "role_based": False,
            "free_email": False
        }
        
        try:
            # Use email-validator library
            validation = ev_validate(email, check_deliverability=True)
            result["valid"] = True
            result["email"] = validation.normalized
            
            # Check MX records
            domain = email.split('@')[1]
            try:
                mx_records = dns.resolver.resolve(domain, 'MX')
                result["mx_records"] = len(mx_records) > 0
                result["deliverable"] = True
            except:
                pass
            
            # Check if disposable/temporary
            result["disposable"] = self._is_disposable(domain)
            
            # Check if role-based (info@, support@, etc.)
            role_prefixes = ['info', 'support', 'contact', 'admin', 'sales', 'hello', 'noreply']
            local_part = email.split('@')[0].lower()
            result["role_based"] = local_part in role_prefixes
            
            # Check if free email provider
            free_domains = ['gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com', 'aol.com']
            result["free_email"] = domain.lower() in free_domains
            
        except EmailNotValidError as e:
            logger.debug(f"Email validation failed for {email}: {str(e)}")
        except Exception as e:
            logger.error(f"Error validating email {email}: {str(e)}")
        
        return result
    
    def enrich_with_hunter(self, email: str) -> Optional[Dict]:
        """
        Enrich email data using Hunter.io API
        Returns additional contact info if found
        """
        if not self.hunter_api_key:
            return None
        
        try:
            url = f"https://api.hunter.io/v2/email-verifier"
            params = {
                "email": email,
                "api_key": self.hunter_api_key
            }
            
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                return data.get("data", {})
        except Exception as e:
            logger.error(f"Hunter.io enrichment failed: {str(e)}")
        
        return None
    
    def find_email_from_domain(self, domain: str, first_name: str = None, last_name: str = None) -> Optional[str]:
        """
        Use Hunter.io to find email pattern for a domain
        """
        if not self.hunter_api_key:
            return None
        
        try:
            url = "https://api.hunter.io/v2/email-finder"
            params = {
                "domain": domain,
                "api_key": self.hunter_api_key
            }
            
            if first_name:
                params["first_name"] = first_name
            if last_name:
                params["last_name"] = last_name
            
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                return data.get("data", {}).get("email")
        except Exception as e:
            logger.error(f"Hunter.io email finder failed: {str(e)}")
        
        return None
    
    def verify_with_neverbounce(self, email: str) -> Optional[Dict]:
        """
        Verify email deliverability with NeverBounce
        """
        if not self.neverbounce_api_key:
            return None
        
        try:
            url = "https://api.neverbounce.com/v4/single/check"
            params = {
                "key": self.neverbounce_api_key,
                "email": email
            }
            
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            logger.error(f"NeverBounce verification failed: {str(e)}")
        
        return None
    
    def _is_disposable(self, domain: str) -> bool:
        """Check if domain is a disposable email provider"""
        disposable_domains = [
            'tempmail.com', '10minutemail.com', 'guerrillamail.com',
            'mailinator.com', 'throwaway.email', 'temp-mail.org'
        ]
        return domain.lower() in disposable_domains
    
    def extract_emails_from_text(self, text: str) -> list:
        """Extract all email addresses from text"""
        pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = re.findall(pattern, text)
        return list(set(emails))  # Remove duplicates


# Utility function
def validate_email_quick(email: str) -> bool:
    """Quick validation function"""
    validator = EmailValidator()
    return validator.basic_validate(email)
