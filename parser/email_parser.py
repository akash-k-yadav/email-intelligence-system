# File: parser/email_parser.py
from dataclasses import dataclass, field
from typing import Dict, List, Optional
import email
from email import policy
from email.parser import BytesParser
import base64
from datetime import datetime

@dataclass
class ParsedEmail:
    id: str
    message_id: str
    from_addr: str
    to_addr: str
    subject: str
    body_text: str
    body_html: str
    date: datetime
    headers: Dict[str, str]
    attachments: List[Dict[str, str]]
    unread: bool = True
    
class EmailParser:
    @staticmethod
    def parse_gmail_message(msg_data):
        """Parse Gmail API message format"""
        raw_email = base64.urlsafe_b64decode(msg_data['raw'])
        email_message = BytesParser(policy=policy.default).parsebytes(raw_email)
        return EmailParser._parse_email_message(email_message, msg_data['id'])
    
    @staticmethod
    def parse_imap_message(msg_data):
        """Parse IMAP message format"""
        email_message = BytesParser(policy=policy.default).parsebytes(msg_data['raw'])
        return EmailParser._parse_email_message(email_message, msg_data['id'])
    
    @staticmethod
    def _parse_email_message(email_message, msg_id):
        # Extract headers
        headers = {}
        for key, value in email_message.items():
            headers[key] = str(value)
        
        # Extract basic fields
        from_addr = email_message.get('From', '')
        to_addr = email_message.get('To', '')
        subject = email_message.get('Subject', '')
        message_id = email_message.get('Message-ID', msg_id)
        
        # Parse date
        date_str = email_message.get('Date', '')
        try:
            date = email.utils.parsedate_to_datetime(date_str)
        except:
            date = datetime.now()
        
        # Extract body
        body_text = ''
        body_html = ''
        attachments = []
        
        if email_message.is_multipart():
            for part in email_message.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get('Content-Disposition', ''))
                
                if 'attachment' in content_disposition:
                    filename = part.get_filename()
                    if filename:
                        attachments.append({
                            'filename': filename,
                            'content_type': content_type,
                            'size': len(part.get_payload(decode=True) or b'')
                        })
                elif content_type == 'text/plain' and not body_text:
                    try:
                        body_text = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                    except:
                        body_text = str(part.get_payload())
                elif content_type == 'text/html' and not body_html:
                    try:
                        body_html = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                    except:
                        body_html = str(part.get_payload())
        else:
            content_type = email_message.get_content_type()
            if content_type == 'text/plain':
                try:
                    body_text = email_message.get_payload(decode=True).decode('utf-8', errors='ignore')
                except:
                    body_text = str(email_message.get_payload())
            elif content_type == 'text/html':
                try:
                    body_html = email_message.get_payload(decode=True).decode('utf-8', errors='ignore')
                except:
                    body_html = str(email_message.get_payload())
        
        return ParsedEmail(
            id=msg_id,
            message_id=message_id,
            from_addr=from_addr,
            to_addr=to_addr,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            date=date,
            headers=headers,
            attachments=attachments,
            unread=True
        )