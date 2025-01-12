import os
import json
from datetime import datetime, timedelta
import requests
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import keys

# Path to token.json file
TOKEN_FILE = "token.json"

# Client ID and Secret from your Google Cloud Console

CLIENT_ID = keys.GOOGLE_CLIENT_ID
CLIENT_SECRET = keys.GOOGLE_CLIENT_SECRET

# Gmail API scope
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']


def load_credentials():
    """Load credentials from the token.json file."""
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'r') as token_file:
            creds_data = json.load(token_file)
            creds = Credentials.from_authorized_user_info(creds_data, SCOPES)
        return creds
    else:
        raise FileNotFoundError(f"{TOKEN_FILE} not found. Perform OAuth first to generate it.")


def save_credentials(creds):
    """Save refreshed credentials back to the token.json file."""
    with open(TOKEN_FILE, 'w') as token_file:
        token_data = {
            "token": creds.token,
            "refresh_token": creds.refresh_token,
            "token_uri": creds.token_uri,
            "client_id": creds.client_id,
            "client_secret": creds.client_secret,
            "scopes": creds.scopes,
        }
        json.dump(token_data, token_file)


def refresh_token_if_needed(creds):
    """Refresh the token if it's expired."""
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        save_credentials(creds)
        print("Token refreshed successfully.")
    elif not creds.valid:
        raise ValueError("Token is invalid, and no refresh token is available.")
    else:
        print("Token is valid.")

import base64

def get_full_email_body(message):
    """Extract the full body of an email."""
    if 'parts' in message['payload']:
        # Multipart email (e.g., HTML + plain text)
        for part in message['payload']['parts']:
            if part['mimeType'] == 'text/plain':
                # Extract plain text body
                body_data = part['body']['data']
                decoded_body = base64.urlsafe_b64decode(body_data).decode('utf-8')
                return decoded_body
            elif part['mimeType'] == 'text/html':
                # Extract HTML body (optional)
                body_data = part['body']['data']
                decoded_body = base64.urlsafe_b64decode(body_data).decode('utf-8')
                return decoded_body
    else:
        # Single-part email
        body_data = message['payload']['body'].get('data', '')
        if body_data:
            decoded_body = base64.urlsafe_b64decode(body_data).decode('utf-8')
            return decoded_body

    return "No body found."

def fetch_emails(creds, last_x_minutes=None, last_n_emails=None):
    """Fetch emails from the Gmail inbox."""
    service = build('gmail', 'v1', credentials=creds)

    user_info = service.users().getProfile(userId='me').execute()
    print(f"Authenticated email: {user_info['emailAddress']}")

    # Construct query based on criteria
    query = ""
    if last_x_minutes:
        time_from = (datetime.utcnow() - timedelta(minutes=last_x_minutes)).isoformat() + "Z"
        query += f"after:{time_from} "
    query = query.strip()

    # Fetch messages
    # results = service.users().messages().list(userId='me', q=query, maxResults=last_n_emails).execute()
    # messages = results.get('messages', [])
    # print(f"Found {len(messages)} messages.")

    results = service.users().messages().list(userId='me').execute()
    messages = results.get('messages', [])
    print(f"Found {len(messages)} messages.")

    for msg in messages:
        message = service.users().messages().get(userId='me', id=msg['id']).execute()
        headers = message['payload']['headers']
        subject = next((header['value'] for header in headers if header['name'] == 'Subject'), None)
        from_email = next((header['value'] for header in headers if header['name'] == 'From'), None)
        snippet = message.get('snippet', '')
        print(f"From: {from_email}\nSubject: {subject}\nSnippet: {snippet}\n")

from datetime import datetime, timedelta, timezone

def get_timestamp_x_minutes_ago(minutes):
    # Get the time X minutes ago in UTC
    time_x_minutes_ago = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    # Convert to UNIX timestamp (integer seconds)
    return int(time_x_minutes_ago.timestamp())

def fetch_emails_with_pagination(service, query):
    page_token = None
    all_messages = []

    while True:
        results = service.users().messages().list(userId='me', q=query, pageToken=page_token).execute()
        messages = results.get('messages', [])
        all_messages.extend(messages)

        page_token = results.get('nextPageToken')
        if not page_token:
            break

    return all_messages


def fetch_emails_from_last_x_minutes(service, minutes):
    """Fetch emails received in the last X minutes and return their details as a dictionary."""
    # Get UNIX timestamp for X minutes ago
    timestamp = get_timestamp_x_minutes_ago(minutes)

    # Create the Gmail API query
    query = f"after:{timestamp}"

    # Fetch messages with pagination
    all_messages = fetch_emails_with_pagination(service, query)

    print(f"Found {len(all_messages)} messages from the last {minutes} minutes.")

    email_details = []

    for msg in all_messages:
        # Get full details for each message
        message = service.users().messages().get(userId='me', id=msg['id']).execute()

        headers = message['payload']['headers']
        subject = next((header['value'] for header in headers if header['name'] == 'Subject'), None)
        from_email = next((header['value'] for header in headers if header['name'] == 'From'), None)
        snippet = message.get('snippet', '')
        full_body = get_full_email_body(message)

        # Append email details as a dictionary
        email_details.append({
            "id": msg['id'],
            "from": from_email,
            "subject": subject,
            "snippet": snippet,
            "body": full_body
        })

    return email_details


def fetch_emails(minutes=30):
    try:
        # Load credentials
        creds = load_credentials()

        # Refresh token if needed
        refresh_token_if_needed(creds)

        # Build Gmail API service
        service = build('gmail', 'v1', credentials=creds)

        # Fetch emails from the last 30 minutes
        emails = fetch_emails_from_last_x_minutes(service, minutes=30)

        # Print all emails in well-formed dictionary

        return emails
        # for email in emails:
        #     print(f"Email ID: {email['id']}")
        #     print(f"From: {email['from']}")
        #     print(f"Subject: {email['subject']}")
        #     print(f"Snippet: {email['snippet']}")
        #     print(f"Body:\n{email['body']}\n")
        #     print("=" * 50)

    except Exception as e:
        print(f"Error: {e}")


def fetch_sms(limit = 10):
    from twilio.rest import Client

    # Your Account SID and Auth Token from https://www.twilio.com/console
    account_sid = keys.TWILIO_account_sid
    auth_token = keys.TWILIO_auth_token
    client = Client(account_sid, auth_token)

    # List recent messages
    messages = client.messages.list(limit=limit)
    return messages

    # for message in messages:
    #     print(f"From: {message.from_}, To: {message.to}, Body: {message.body}")

