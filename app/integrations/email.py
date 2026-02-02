"""
Email integration utilities
"""
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import asyncio
import aiohttp
from typing import Optional

async def send_email_via_sendgrid(to_email: str, subject: str, body: str) -> bool:
    """
    Send email via SendGrid API
    """
    sendgrid_api_key = os.getenv("SENDGRID_API_KEY")
    
    if not sendgrid_api_key:
        print("SendGrid API key not configured")
        return False
    
    url = "https://api.sendgrid.com/v3/mail/send"
    
    payload = {
        "personalizations": [
            {
                "to": [{"email": to_email}],
                "subject": subject
            }
        ],
        "from": {"email": os.getenv("SENDER_EMAIL", "sender@example.com")},
        "content": [
            {
                "type": "text/plain",
                "value": body
            }
        ]
    }
    
    headers = {
        "Authorization": f"Bearer {sendgrid_api_key}",
        "Content-Type": "application/json"
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as response:
                if response.status in [200, 202]:
                    return True
                else:
                    print(f"SendGrid error: {response.status}, {await response.text()}")
                    return False
    except Exception as e:
        print(f"SendGrid exception: {str(e)}")
        return False

async def send_email_via_smtp(to_email: str, subject: str, body: str) -> bool:
    """
    Send email via SMTP
    """
    smtp_server = os.getenv("SMTP_SERVER", "localhost")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_username = os.getenv("SMTP_USERNAME")
    smtp_password = os.getenv("SMTP_PASSWORD")
    sender_email = os.getenv("SENDER_EMAIL")
    
    if not all([smtp_username, smtp_password, sender_email]):
        print("SMTP credentials not fully configured")
        return False
    
    try:
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = to_email
        msg['Subject'] = subject
        
        msg.attach(MIMEText(body, 'plain'))
        
        # For now, we'll run the SMTP operation in a thread pool since smtplib is sync
        import asyncio
        from concurrent.futures import ThreadPoolExecutor

        def send_sync():
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()
            server.login(smtp_username, smtp_password)
            text = msg.as_string()
            server.sendmail(sender_email, to_email, text)
            server.quit()
            return True

        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            result = await loop.run_in_executor(executor, send_sync)

        return result
    except Exception as e:
        print(f"SMTP error: {str(e)}")
        return False