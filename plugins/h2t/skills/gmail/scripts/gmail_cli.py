#!/usr/bin/env python3
"""
Gmail CLI - Command-line interface for Gmail API
Supports reading, sending, searching emails and managing labels
"""

import os
import sys
import json
import base64
import argparse
from pathlib import Path
from typing import Optional, List, Dict, Any
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import re

from dotenv import load_dotenv
load_dotenv(Path.home() / '.dor' / 'secrets.env', override=False)

# Google API imports
try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
except ImportError:
    print("Error: Google API libraries not found.", file=sys.stderr)
    print("Install: pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client", file=sys.stderr)
    sys.exit(1)

# Gmail API scopes
SCOPES = [
    # Gmail scopes
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/gmail.labels',
    # Google Calendar scopes (для совместимости с calendar skill)
    'https://www.googleapis.com/auth/calendar',
]


class GmailClient:
    """Gmail API client"""

    def __init__(self):
        """Initialize Gmail client with OAuth credentials"""
        self.service = self._get_service()

    def _get_service(self):
        """Get Gmail API service with authentication"""
        creds = None

        # Try to use shared Google credentials first (from google-calendar-mcp)
        shared_config = Path.home() / '.config' / 'google-calendar-mcp'
        gmail_config = Path.home() / '.config' / 'gmail'

        # Determine which config directory to use
        if (shared_config / 'credentials.json').exists():
            config_dir = shared_config
            token_path = config_dir / 'tokens.json'  # Note: plural for google-calendar-mcp
            creds_path = config_dir / 'credentials.json'
        else:
            config_dir = gmail_config
            token_path = config_dir / 'token.json'
            creds_path = config_dir / 'credentials.json'

        # Load existing token
        if token_path.exists():
            try:
                with open(token_path) as f:
                    token_data = json.load(f)

                # Handle legacy nested format @cocal/google-calendar-mcp
                if 'normal' in token_data:
                    token_data = token_data['normal']
                    # Convert expiry_date (ms) → expiry (ISO)
                    if 'expiry_date' in token_data:
                        expiry_ms = token_data.pop('expiry_date')
                        expiry_dt = datetime.fromtimestamp(expiry_ms / 1000)
                        token_data['expiry'] = expiry_dt.isoformat() + 'Z'
                    # Normalize scope string → scopes list
                    if 'scope' in token_data:
                        token_data.setdefault('scopes', token_data.pop('scope').split())

                # Merge client credentials if not embedded in token
                if 'client_id' not in token_data and creds_path.exists():
                    with open(creds_path) as f:
                        creds_data = json.load(f)
                    installed = creds_data.get('installed', creds_data)
                    token_data['client_id'] = installed['client_id']
                    token_data['client_secret'] = installed['client_secret']
                    token_data.setdefault('token_uri', installed.get('token_uri', 'https://oauth2.googleapis.com/token'))

                # Always use scopes from token to avoid invalid_scope on refresh
                effective_scopes = token_data.get('scopes') or SCOPES
                creds = Credentials.from_authorized_user_info(token_data, effective_scopes)
            except Exception as e:
                print(f"Warning: Could not load token: {e}", file=sys.stderr)
                creds = None

        # Refresh or get new token
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception as e:
                    print(f"Token refresh failed: {e}", file=sys.stderr)
                    print("Please delete token.json and re-authenticate", file=sys.stderr)
                    raise RuntimeError(f"Gmail token refresh failed: {e}") from e
            else:
                if not creds_path.exists():
                    print(f"Error: credentials.json not found at {creds_path}", file=sys.stderr)
                    print("Please download OAuth credentials from Google Cloud Console", file=sys.stderr)
                    sys.exit(1)

                flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES)
                creds = flow.run_local_server(port=0)

            # Save token
            config_dir.mkdir(parents=True, exist_ok=True)
            token_path.write_text(creds.to_json())

        return build('gmail', 'v1', credentials=creds)

    def list_messages(self, max_results: int = 10, query: Optional[str] = None,
                     unread_only: bool = False) -> List[Dict[str, Any]]:
        """List messages in the mailbox"""
        try:
            # Build query
            if unread_only and query:
                query = f"is:unread {query}"
            elif unread_only:
                query = "is:unread"

            # Get messages
            results = self.service.users().messages().list(
                userId='me',
                maxResults=max_results,
                q=query
            ).execute()

            messages = results.get('messages', [])

            # Get full message details
            detailed_messages = []
            for msg in messages:
                msg_detail = self.get_message(msg['id'])
                detailed_messages.append(msg_detail)

            return detailed_messages

        except HttpError as error:
            raise Exception(f"Gmail API error: {error}")

    def get_message(self, message_id: str) -> Dict[str, Any]:
        """Get a specific message by ID"""
        try:
            message = self.service.users().messages().get(
                userId='me',
                id=message_id,
                format='full'
            ).execute()

            return self._parse_message(message)

        except HttpError as error:
            raise Exception(f"Failed to get message {message_id}: {error}")

    def _parse_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Parse Gmail message into readable format"""
        headers = {h['name']: h['value'] for h in message['payload']['headers']}

        parsed = {
            'id': message['id'],
            'threadId': message['threadId'],
            'labelIds': message.get('labelIds', []),
            'snippet': message.get('snippet', ''),
            'from': headers.get('From', ''),
            'to': headers.get('To', ''),
            'subject': headers.get('Subject', ''),
            'date': headers.get('Date', ''),
            'body': self._get_message_body(message['payload'])
        }

        return parsed

    def _get_message_body(self, payload: Dict[str, Any]) -> str:
        """Extract message body from payload"""
        if 'body' in payload and 'data' in payload['body']:
            return base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8')

        if 'parts' in payload:
            for part in payload['parts']:
                if part['mimeType'] == 'text/plain':
                    if 'data' in part['body']:
                        return base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
                elif part['mimeType'] == 'text/html':
                    if 'data' in part['body']:
                        html = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
                        return self._html_to_text(html)
                elif 'parts' in part:
                    # Recursive for nested parts
                    body = self._get_message_body(part)
                    if body:
                        return body

        return ""

    def _html_to_text(self, html: str) -> str:
        """Convert HTML to plain text (simple version)"""
        # Remove script and style tags
        text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)

        # Replace <br> and <p> with newlines
        text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'</p>', '\n\n', text, flags=re.IGNORECASE)

        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)

        # Decode HTML entities
        import html as html_module
        text = html_module.unescape(text)

        # Clean up whitespace
        text = re.sub(r'\n\s*\n', '\n\n', text)
        text = text.strip()

        return text

    def search_messages(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """Search messages with Gmail query syntax"""
        return self.list_messages(max_results=max_results, query=query)

    def send_message(self, to: str, subject: str, body: str,
                    attachments: Optional[List[str]] = None,
                    as_draft: bool = False,
                    thread_id: Optional[str] = None,
                    reply_to_message_id: Optional[str] = None) -> Dict[str, Any]:
        """Send an email message or create a draft.

        For thread replies, pass thread_id and optionally reply_to_message_id
        (the RFC 2822 Message-ID header of the message being replied to).
        """
        try:
            message = MIMEMultipart() if attachments else MIMEText(body)

            message['to'] = to
            message['subject'] = subject

            # Thread reply headers (RFC 2822)
            if reply_to_message_id:
                message['In-Reply-To'] = reply_to_message_id
                message['References'] = reply_to_message_id

            # Add body for multipart
            if attachments:
                message.attach(MIMEText(body, 'plain'))
                for file_path in attachments:
                    self._attach_file(message, file_path)

            # Encode message
            raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

            if as_draft:
                draft_body: Dict[str, Any] = {'raw': raw}
                if thread_id:
                    draft_body['threadId'] = thread_id
                result = self.service.users().drafts().create(
                    userId='me',
                    body={'message': draft_body}
                ).execute()
            else:
                send_body: Dict[str, Any] = {'raw': raw}
                if thread_id:
                    send_body['threadId'] = thread_id
                result = self.service.users().messages().send(
                    userId='me',
                    body=send_body
                ).execute()

            return result

        except HttpError as error:
            raise Exception(f"Failed to {'create draft' if as_draft else 'send message'}: {error}")

    def _attach_file(self, message: MIMEMultipart, file_path: str):
        """Attach a file to message"""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Attachment not found: {file_path}")

        with open(path, 'rb') as f:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(f.read())

        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f'attachment; filename={path.name}')
        message.attach(part)

    def list_labels(self) -> List[Dict[str, str]]:
        """List all labels in mailbox"""
        try:
            results = self.service.users().labels().list(userId='me').execute()
            return results.get('labels', [])
        except HttpError as error:
            raise Exception(f"Failed to list labels: {error}")

    def modify_labels(self, message_id: str, add_labels: Optional[List[str]] = None,
                     remove_labels: Optional[List[str]] = None) -> Dict[str, Any]:
        """Add or remove labels from a message"""
        try:
            body = {}
            if add_labels:
                body['addLabelIds'] = add_labels
            if remove_labels:
                body['removeLabelIds'] = remove_labels

            result = self.service.users().messages().modify(
                userId='me',
                id=message_id,
                body=body
            ).execute()

            return result

        except HttpError as error:
            raise Exception(f"Failed to modify labels: {error}")


def format_message_list(messages: List[Dict[str, Any]]) -> str:
    """Format message list for display"""
    if not messages:
        return "No messages found."

    output = []
    output.append(f"Found {len(messages)} message(s):\n")

    for i, msg in enumerate(messages, 1):
        is_unread = 'UNREAD' in msg.get('labelIds', [])
        unread_mark = '📩 ' if is_unread else '   '

        output.append(f"{unread_mark}{i}. **{msg['subject']}**")
        output.append(f"   From: {msg['from']}")
        output.append(f"   Date: {msg['date']}")
        output.append(f"   ID: `{msg['id']}`")
        output.append(f"   Snippet: {msg['snippet'][:100]}...")
        output.append("")

    return '\n'.join(output)


def format_message_detail(message: Dict[str, Any]) -> str:
    """Format single message for display"""
    output = []
    output.append(f"# {message['subject']}\n")
    output.append(f"**From:** {message['from']}")
    output.append(f"**To:** {message['to']}")
    output.append(f"**Date:** {message['date']}")
    output.append(f"**Labels:** {', '.join(message.get('labelIds', []))}")
    output.append(f"\n---\n")
    output.append(message['body'])

    return '\n'.join(output)


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description='Gmail CLI - Work with Gmail API from command line',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    subparsers = parser.add_subparsers(dest='command', help='Command to execute')

    # List command
    list_parser = subparsers.add_parser('list', help='List messages')
    list_parser.add_argument('--max', type=int, default=10, help='Maximum messages to retrieve')
    list_parser.add_argument('--unread', action='store_true', help='Show only unread messages')
    list_parser.add_argument('--query', help='Gmail search query')

    # Read command
    read_parser = subparsers.add_parser('read', help='Read a message')
    read_parser.add_argument('message_id', help='Message ID')
    read_parser.add_argument('--format', choices=['plain', 'json'], default='plain',
                           help='Output format')

    # Search command
    search_parser = subparsers.add_parser('search', help='Search messages')
    search_parser.add_argument('query', help='Gmail search query')
    search_parser.add_argument('--max', type=int, default=10, help='Maximum results')

    # Send command
    send_parser = subparsers.add_parser('send', help='Send a message')
    send_parser.add_argument('to', help='Recipient email')
    send_parser.add_argument('subject', help='Email subject')
    send_parser.add_argument('body', nargs='?', help='Email body')
    send_parser.add_argument('--file', help='Read body from file')
    send_parser.add_argument('--attach', nargs='+', help='Attachment files')
    send_parser.add_argument('--draft', action='store_true',
                           help='Create draft instead of sending')

    # Draft command (alias for send --draft)
    draft_parser = subparsers.add_parser('draft', help='Create a draft message')
    draft_parser.add_argument('to', help='Recipient email')
    draft_parser.add_argument('subject', help='Email subject')
    draft_parser.add_argument('body', nargs='?', help='Email body')
    draft_parser.add_argument('--file', help='Read body from file')
    draft_parser.add_argument('--attach', nargs='+', help='Attachment files')
    draft_parser.add_argument('--thread-id', help='Gmail thread ID to reply in')
    draft_parser.add_argument('--reply-to', help='RFC 2822 Message-ID of message being replied to')

    # Labels command
    labels_parser = subparsers.add_parser('labels', help='List all labels')

    # Label command (modify)
    label_parser = subparsers.add_parser('label', help='Modify message labels')
    label_parser.add_argument('message_id', help='Message ID')
    label_parser.add_argument('--add', nargs='+', help='Labels to add')
    label_parser.add_argument('--remove', nargs='+', help='Labels to remove')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    try:
        client = GmailClient()

        if args.command == 'list':
            messages = client.list_messages(
                max_results=args.max,
                query=args.query,
                unread_only=args.unread
            )
            print(format_message_list(messages))

        elif args.command == 'read':
            message = client.get_message(args.message_id)
            if args.format == 'json':
                print(json.dumps(message, indent=2, ensure_ascii=False))
            else:
                print(format_message_detail(message))

        elif args.command == 'search':
            messages = client.search_messages(args.query, max_results=args.max)
            print(format_message_list(messages))

        elif args.command == 'send':
            body = args.body
            if args.file:
                with open(args.file, 'r', encoding='utf-8') as f:
                    body = f.read()

            if not body:
                print("Error: Either provide body as argument or use --file", file=sys.stderr)
                return 1

            is_draft = getattr(args, 'draft', False)
            result = client.send_message(
                to=args.to,
                subject=args.subject,
                body=body,
                attachments=args.attach,
                as_draft=is_draft
            )

            if is_draft:
                print(f"✓ Draft created successfully (ID: {result['id']})")
                print(f"  View in Gmail: https://mail.google.com/mail/u/0/#drafts")
            else:
                print(f"✓ Message sent successfully (ID: {result['id']})")

        elif args.command == 'draft':
            body = args.body
            if args.file:
                with open(args.file, 'r', encoding='utf-8') as f:
                    body = f.read()

            if not body:
                print("Error: Either provide body as argument or use --file", file=sys.stderr)
                return 1

            result = client.send_message(
                to=args.to,
                subject=args.subject,
                body=body,
                attachments=args.attach,
                as_draft=True,
                thread_id=getattr(args, 'thread_id', None),
                reply_to_message_id=getattr(args, 'reply_to', None),
            )
            print(f"✓ Draft created successfully (ID: {result['id']})")
            print(f"  View in Gmail: https://mail.google.com/mail/u/0/#drafts")

        elif args.command == 'labels':
            labels = client.list_labels()
            print(f"Found {len(labels)} label(s):\n")
            for label in labels:
                print(f"- {label['name']} (ID: {label['id']})")

        elif args.command == 'label':
            result = client.modify_labels(
                message_id=args.message_id,
                add_labels=args.add,
                remove_labels=args.remove
            )
            print(f"✓ Labels modified successfully")
            print(f"Current labels: {', '.join(result.get('labelIds', []))}")

        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
