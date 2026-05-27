# Google OAuth Configuration Module
# This module handles Google OAuth setup and token management

import os
import json
import pickle
from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.exceptions import RefreshError

# ============================================================================
# GOOGLE OAUTH CONFIGURATION
# ============================================================================

# Paths for credentials and tokens
GOOGLE_OAUTH_CREDENTIALS = 'google_oauth_credentials.json'
GOOGLE_OAUTH_TOKEN = 'google_oauth_token.pickle'

# OAuth scopes - permissions we're requesting
OAUTH_SCOPES = ['openid', 'email', 'profile']

# OAuth configuration (will be loaded from credentials file)
oauth_flow = None
oauth_service = None


def create_oauth_flow():
    """
    Create and return Google OAuth flow
    This requires google_oauth_credentials.json to exist
    """
    global oauth_flow
    
    if not os.path.exists(GOOGLE_OAUTH_CREDENTIALS):
        raise FileNotFoundError(
            f"❌ {GOOGLE_OAUTH_CREDENTIALS} not found!\n"
            "Please download it from Google Cloud Console and place it in the project root."
        )
    
    try:
        oauth_flow = Flow.from_client_secrets_file(
            GOOGLE_OAUTH_CREDENTIALS,
            scopes=OAUTH_SCOPES,
            redirect_uri='http://localhost:5000/auth/callback'
        )
        return oauth_flow
    except Exception as e:
        print(f"❌ Error creating OAuth flow: {e}")
        return None


def get_authorization_url():
    """
    Get the Google OAuth authorization URL
    User should visit this URL to authorize the app
    """
    try:
        flow = create_oauth_flow()
        if not flow:
            return None
        
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent'
        )
        
        return authorization_url, state
    except Exception as e:
        print(f"❌ Error getting authorization URL: {e}")
        return None


def exchange_code_for_token(authorization_response, state):
    """
    Exchange authorization code for access token
    Called after user authorizes the app
    """
    try:
        flow = create_oauth_flow()
        if not flow:
            return None
        
        # Exchange code for credentials
        flow.fetch_token(authorization_response=authorization_response)
        
        credentials = flow.credentials
        
        # Save token for future use
        save_token(credentials)
        
        return credentials
    except Exception as e:
        print(f"❌ Error exchanging code for token: {e}")
        return None


def load_token():
    """Load saved OAuth token from pickle file"""
    try:
        if not os.path.exists(GOOGLE_OAUTH_TOKEN):
            return None
        
        with open(GOOGLE_OAUTH_TOKEN, 'rb') as token_file:
            credentials = pickle.load(token_file)
        
        # Refresh if expired
        if credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
            save_token(credentials)
        
        return credentials
    except Exception as e:
        print(f"❌ Error loading token: {e}")
        return None


def save_token(credentials):
    """Save OAuth token to pickle file"""
    try:
        with open(GOOGLE_OAUTH_TOKEN, 'wb') as token_file:
            pickle.dump(credentials, token_file)
        print("✓ Token saved successfully")
    except Exception as e:
        print(f"❌ Error saving token: {e}")


def get_user_info(credentials):
    """
    Get user info from Google using credentials
    Returns email, name, picture, etc.
    """
    try:
        import requests
        
        url = r"https://www.googleapis.com/oauth2/v1/userinfo"
        headers = {'Authorization': f'Bearer {credentials.token}'}
        
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"❌ Error getting user info: {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Error in get_user_info: {e}")
        return None


def is_token_valid():
    """Check if saved token exists and is valid"""
    credentials = load_token()
    return credentials is not None


def clear_token():
    """Clear saved token (for logout)"""
    try:
        if os.path.exists(GOOGLE_OAUTH_TOKEN):
            os.remove(GOOGLE_OAUTH_TOKEN)
            print("✓ Token cleared")
            return True
    except Exception as e:
        print(f"❌ Error clearing token: {e}")
        return False


# ============================================================================
# Helper function to setup initial config
# ============================================================================

def setup_oauth_config(client_id, client_secret, redirect_uri='http://localhost:5000/auth/callback'):
    """
    Setup OAuth configuration programmatically
    Useful if you want to provide credentials at runtime
    """
    config = {
        'installed': {
            'client_id': client_id,
            'client_secret': client_secret,
            'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
            'token_uri': 'https://oauth2.googleapis.com/token',
            'redirect_uris': [redirect_uri],
            'auth_provider_x509_cert_url': 'https://www.googleapis.com/oauth2/v1/certs'
        }
    }
    
    try:
        with open(GOOGLE_OAUTH_CREDENTIALS, 'w') as f:
            json.dump(config, f, indent=2)
        print("✓ OAuth configuration saved")
        return True
    except Exception as e:
        print(f"❌ Error saving OAuth config: {e}")
        return False


if __name__ == '__main__':
    print("Google OAuth Configuration Module")
    print("================================")
    print("\nThis module provides:")
    print("  - OAuth flow initialization")
    print("  - Token management")
    print("  - User info retrieval")
    print("\nUsage:")
    print("  from google_oauth_config import *")
    print("  auth_url, state = get_authorization_url()")
    print("  credentials = exchange_code_for_token(response, state)")
    print("  user_info = get_user_info(credentials)")
