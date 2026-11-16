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
    """Find the React build directory (frontend/dist copied into backend during build)."""
    candidates = [
        BASE_DIR / 'frontend' / 'dist',       # Render: copied here by build.sh
        BASE_DIR.parent / 'frontend' / 'dist', # fallback: project root structure
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

is_render_or_prod = os.getenv('RENDER') is not None or os.getenv('PORT') is not None

APP_CONFIG = {
    'MAX_CONTENT_LENGTH': 500 * 1024 * 1024,
    'SECRET_KEY': os.getenv('SECRET_KEY', 'pothole_detection_secret_key_2024'),
    'SESSION_COOKIE_HTTPONLY': True,
    # Supports cross-subdomain cookies on Render (e.g. frontend.onrender.com -> backend.onrender.com)
    'SESSION_COOKIE_SAMESITE': 'None' if is_render_or_prod else 'Lax',
    'SESSION_COOKIE_SECURE': True if is_render_or_prod else False,
    'PERMANENT_SESSION_LIFETIME': timedelta(days=7),
}


def configure_cors(app):
    """Configure CORS for local dev and Render deployments."""
    if HAS_CORS:
        import re
        allowed_origins = [
            'http://localhost:5173',
            'http://127.0.0.1:5173',
            'http://localhost:3000',
            'http://127.0.0.1:3000',
            'https://pothole-detection-2-sc8w.onrender.com',
            re.compile(r'^https:\/\/.*\.onrender\.com$'),
        ]
        extra = os.getenv('CORS_ORIGINS', '')
        if extra:
            allowed_origins.extend([o.strip() for o in extra.split(',') if o.strip()])
        CORS(
            app,
            supports_credentials=True,
            origins=allowed_origins,
            allow_headers=['Content-Type', 'Authorization', 'Accept', 'X-Requested-With', 'X-Auth-Token'],
            expose_headers=['Content-Type', 'Authorization'],
            methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
        )
