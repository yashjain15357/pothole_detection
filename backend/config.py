import os
import re
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

# Supported media extensions
SUPPORTED_IMAGES = {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.jfif'}
SUPPORTED_VIDEOS = {'.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv', '.mpeg', '.mpg', '.m4v'}

APP_CONFIG = {
    'MAX_CONTENT_LENGTH': 500 * 1024 * 1024,
    'SECRET_KEY': os.getenv('SECRET_KEY', 'change_this_to_a_real_secret'),
    'SESSION_COOKIE_HTTPONLY': True,
    'SESSION_COOKIE_SAMESITE': 'None',
    'SESSION_COOKIE_SECURE': True,
    'PERMANENT_SESSION_LIFETIME': timedelta(days=7),
}

def configure_cors(app):
    if HAS_CORS:
        allowed_origins = [
            'http://localhost:5173',
            'http://127.0.0.1:5173',
            'http://localhost:3000',
            'http://127.0.0.1:3000',
            'https://pothole-detection-hfy3-git-main-jainy9089-4487s-projects.vercel.app',
            re.compile(r'^https:\/\/.*\.vercel\.app$'),
        ]

        render_url = os.getenv('RENDER_EXTERNAL_URL')
        if render_url:
            allowed_origins.append(render_url)

        extra = os.getenv('CORS_ORIGINS', '')
        if extra:
            allowed_origins.extend([o.strip() for o in extra.split(',') if o.strip()])

        CORS(
            app,
            supports_credentials=True,
            origins=allowed_origins,
            methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
            allow_headers=["Content-Type", "Authorization", "Accept", "X-Requested-With"]
        )