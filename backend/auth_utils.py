import json
import os
import sqlite3
from functools import wraps
from pathlib import Path

from flask import jsonify, redirect, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from database import DATABASE

USERS = {
    'admin': 'admin123',
    'user': 'user123',
    'demo': 'demo123',
}


def get_db_connection():
    """Return a SQLite connection for auth-related database operations."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_user_table():
    """Create the users table if it does not exist and seed the demo users."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            email TEXT UNIQUE,
            password_hash TEXT NOT NULL,
            full_name TEXT,
            role TEXT DEFAULT 'user',
            is_active INTEGER DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    c.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username ON users(username)')
    c.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(email)')
    conn.commit()

    for username, password in USERS.items():
        existing = c.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()
        if not existing:
            c.execute(
                'INSERT INTO users (username, email, password_hash, full_name, role) VALUES (?, ?, ?, ?, ?)',
                (username, f'{username}@example.com', generate_password_hash(password), username.title(), 'admin' if username == 'admin' else 'user')
            )

    conn.commit()
    conn.close()


def create_user(username, password, email=None, full_name=None, role='user'):
    """Create a new user account with a hashed password."""
    username = (username or '').strip()
    email = (email or '').strip()
    full_name = (full_name or '').strip() or username

    if not username or not password:
        return None, 'Username and password are required'

    if len(password) < 6:
        return None, 'Password must be at least 6 characters long'

    if len(username) < 3:
        return None, 'Username must be at least 3 characters long'

    ensure_user_table()
    conn = get_db_connection()
    c = conn.cursor()

    if c.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone():
        conn.close()
        return None, 'Username already exists'

    if email and c.execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone():
        conn.close()
        return None, 'Email already registered'

    hashed = generate_password_hash(password)
    c.execute(
        'INSERT INTO users (username, email, password_hash, full_name, role) VALUES (?, ?, ?, ?, ?)',
        (username, email or None, hashed, full_name, role)
    )
    user_id = c.lastrowid
    conn.commit()
    conn.close()

    return {
        'id': user_id,
        'username': username,
        'email': email or '',
        'full_name': full_name,
        'role': role,
    }, None


def get_user_by_username(username):
    """Fetch user data by username."""
    if not username:
        return None
    ensure_user_table()
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE username = ?', (username.strip(),)).fetchone()
    conn.close()
    return dict(user) if user else None


def get_user_by_id(user_id):
    """Fetch user data by user id."""
    if not user_id:
        return None
    ensure_user_table()
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    return dict(user) if user else None


def verify_user_login(username, password):
    """Validate a username/password pair against the database."""
    username = (username or '').strip()
    if not username or not password:
        return None, 'Username and password are required'

    ensure_user_table()
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
    conn.close()

    if not user:
        return None, 'Invalid username or password'

    user_data = dict(user)
    if not check_password_hash(user_data['password_hash'], password):
        return None, 'Invalid username or password'

    if not user_data.get('is_active', 1):
        return None, 'This account is disabled'

    user_data.pop('password_hash', None)
    return user_data, None


def get_session_user():
    """Return the current authenticated user from Flask session."""
    user_id = session.get('user_id')
    if not user_id:
        return None
    return get_user_by_id(user_id)


def load_google_oauth_credentials():
    """Load Google OAuth client credentials from environment variables or a local JSON file."""
    client_id = os.getenv('GOOGLE_CLIENT_ID', '').strip()
    client_secret = os.getenv('GOOGLE_CLIENT_SECRET', '').strip()

    credentials_file = Path('google_oauth_credentials.json')
    if credentials_file.exists() and (not client_id or not client_secret):
        try:
            with open(credentials_file, 'r', encoding='utf-8') as file:
                config = json.load(file)

            oauth_config = config.get('installed') or config.get('web') or {}
            client_id = client_id or str(oauth_config.get('client_id', '')).strip()
            client_secret = client_secret or str(oauth_config.get('client_secret', '')).strip()
        except Exception as error:
            print(f"Failed to load Google OAuth credentials from file: {error}")

    return client_id, client_secret


def register_google_oauth(oauth):
    """Register the Google OAuth client only when credentials are available."""
    client_id, client_secret = load_google_oauth_credentials()

    if not client_id or not client_secret:
        print(
            'Google OAuth is not configured. Set GOOGLE_CLIENT_ID and '
            'GOOGLE_CLIENT_SECRET or add an ignored google_oauth_credentials.json file.'
        )
        return None

    return oauth.register(
        name='google',
        client_id=client_id,
        client_secret=client_secret,
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        client_kwargs={'scope': 'openid email profile'},
    )


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            if (
                request.path.startswith('/api/') or
                request.is_json or
                request.headers.get('Accept') == 'application/json' or
                request.headers.get('X-Requested-With') == 'XMLHttpRequest' or
                request.path in [
                    '/upload-image', '/upload-video', '/detect-frame',
                    '/start-camera-session', '/save-camera-report',
                    '/save-location-with-report', '/save-video-location-with-report',
                    '/send-report-email', '/reports', '/reports-stats'
                ]
            ):
                return jsonify({'success': False, 'error': 'Authentication required', 'authenticated': False}), 401
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function
