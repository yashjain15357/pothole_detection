import os
from datetime import timedelta
from pathlib import Path

try:
    from flask_cors import CORS
    HAS_CORS = True
except ImportError:
    CORS = None
    HAS_CORS = False

BASE_DIR = Path(__file__).resolve().parent

def get_react_dist_dir():
    candidates = [
        BASE_DIR.parent / 'frontend' / 'dist',
        BASE_DIR / 'frontend' / 'dist',
        BASE_DIR / 'dist',
    ]
    for c in candidates:
        if (c / 'index.html').exists():
            return c
    return candidates[0]

REACT_DIST_DIR = get_react_dist_dir()

SUPPORTED_IMAGES = ('.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff')
SUPPORTED_VIDEOS = ('.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv')

SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
SMTP_EMAIL = os.getenv('SMTP_EMAIL', '').strip()
SMTP_APP_PASSWORD = os.getenv('SMTP_APP_PASSWORD', '').strip()
SMTP_USE_STARTTLS = os.getenv('SMTP_USE_STARTTLS', 'true').lower() in ('1', 'true', 'yes')

APP_CONFIG = {
    'MAX_CONTENT_LENGTH': 500 * 1024 * 1024,
    'SECRET_KEY': os.getenv('SECRET_KEY', 'pothole_detection_secret_key_2024'),
    'SESSION_COOKIE_HTTPONLY': True,
    'SESSION_COOKIE_SAMESITE': 'Lax',
    # Enable secure cookies on any hosted environment (Render, Railway, etc.)
    'SESSION_COOKIE_SECURE': os.getenv('RENDER') is not None or os.getenv('RAILWAY_ENVIRONMENT') is not None,
    'PERMANENT_SESSION_LIFETIME': timedelta(days=7),
}


def configure_cors(app):
    if HAS_CORS:
        # Build allowed origins: always include localhost, plus hosted platform URLs
        allowed_origins = [
            'http://localhost:5173',
            'http://127.0.0.1:5173',
            'http://localhost:3000',
            'http://127.0.0.1:3000',
        ]
        # Railway
        railway_url = os.getenv('RAILWAY_PUBLIC_DOMAIN')
        if railway_url:
            allowed_origins.append(f'https://{railway_url}')
        # Render
        render_url = os.getenv('RENDER_EXTERNAL_URL')
        if render_url:
            allowed_origins.append(render_url)
        # Also support custom CORS_ORIGINS env var (comma-separated)
        extra = os.getenv('CORS_ORIGINS', '')
        if extra:
            allowed_origins.extend([o.strip() for o in extra.split(',') if o.strip()])
        CORS(
            app,
            supports_credentials=True,
            origins=allowed_origins,
        )
