import json
import os
import sqlite3
from functools import wraps
from pathlib import Path

from flask import jsonify, redirect, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

from database import DATABASE, get_db_connection, is_postgres_db

USERS = {
    'admin': 'admin123',
    'user': 'user123',
    'demo': 'demo123',
}


def row_to_dict(row, cursor):
    """Convert sqlite/psycopg row objects to a dict."""
    if row is None:
        return None
    if hasattr(row, 'keys'):
        return dict(row)
    columns = [col[0] for col in cursor.description]
    return dict(zip(columns, row))


def get_db_connection_for_auth():
    """Return a DB connection; PostgreSQL-safe but compatible with SQLite local dev."""
    conn = get_db_connection()
    if is_postgres_db():
        conn.autocommit = False
    else:
        conn.row_factory = sqlite3.Row
    return conn


def ensure_user_table():
    """Create the users table if it does not exist and seed the demo users."""
    conn = get_db_connection_for_auth()
    c = conn.cursor()
    if is_postgres_db():
        c.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id BIGSERIAL PRIMARY KEY,
                username VARCHAR(150) NOT NULL UNIQUE,
                email VARCHAR(255) UNIQUE,
                password_hash TEXT NOT NULL,
                full_name VARCHAR(255),
                role VARCHAR(50) DEFAULT 'user',
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
    else:
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
        if is_postgres_db():
            c.execute('SELECT id FROM users WHERE username = %s', (username,))
            existing = c.fetchone()
        else:
            c.execute('SELECT id FROM users WHERE username = ?', (username,))
            existing = c.fetchone()
        if not existing:
            if is_postgres_db():
                c.execute(
                    'INSERT INTO users (username, email, password_hash, full_name, role) VALUES (%s, %s, %s, %s, %s)',
                    (username, f'{username}@example.com', generate_password_hash(password), username.title(), 'admin' if username == 'admin' else 'user')
                )
            else:
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
    conn = get_db_connection_for_auth()
    c = conn.cursor()

    if is_postgres_db():
        c.execute('SELECT id FROM users WHERE username = %s', (username,))
        existing = c.fetchone()
        if existing:
            conn.close(); return None, 'Username already exists'
        if email:
            c.execute('SELECT id FROM users WHERE email = %s', (email,))
            existing_email = c.fetchone()
            if existing_email:
                conn.close(); return None, 'Email already registered'

        hashed = generate_password_hash(password)
        c.execute(
            'INSERT INTO users (username, email, password_hash, full_name, role) VALUES (%s, %s, %s, %s, %s)',
            (username, email or None, hashed, full_name, role)
        )
        user_id = c.fetchone()[0] if c.description else None
    else:
        c.execute('SELECT id FROM users WHERE username = ?', (username,))
        if c.fetchone():
            conn.close(); return None, 'Username already exists'
        if email:
            c.execute('SELECT id FROM users WHERE email = ?', (email,))
            if c.fetchone():
                conn.close(); return None, 'Email already registered'

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
    conn = get_db_connection_for_auth()
    c = conn.cursor()
    if is_postgres_db():
        c.execute('SELECT * FROM users WHERE username = %s', (username.strip(),))
        user = c.fetchone()
    else:
        c.execute('SELECT * FROM users WHERE username = ?', (username.strip(),))
        user = c.fetchone()
    conn.close()
    if not user:
        return None
    if hasattr(user, 'keys'):
        return dict(user)
    return row_to_dict(user, c)


def get_user_by_id(user_id):
    """Fetch user data by user id."""
    if not user_id:
        return None
    ensure_user_table()
    conn = get_db_connection_for_auth()
    c = conn.cursor()
    if is_postgres_db():
        c.execute('SELECT * FROM users WHERE id = %s', (user_id,))
        user = c.fetchone()
    else:
        c.execute('SELECT * FROM users WHERE id = ?', (user_id,))
        user = c.fetchone()
    conn.close()
    if not user:
        return None
    if hasattr(user, 'keys'):
        return dict(user)
    return row_to_dict(user, c)


def verify_user_login(username, password):
    """Validate a username/password pair against the database."""
    username = (username or '').strip()
    if not username or not password:
        return None, 'Username and password are required'

    ensure_user_table()
    conn = get_db_connection_for_auth()
    c = conn.cursor()
    if is_postgres_db():
        c.execute('SELECT * FROM users WHERE username = %s', (username,))
        user = c.fetchone()
    else:
        c.execute('SELECT * FROM users WHERE username = ?', (username,))
        user = c.fetchone()
    conn.close()

    if not user:
        return None, 'Invalid username or password'

    user_data = row_to_dict(user, c) if not hasattr(user, 'keys') else dict(user)
    if not check_password_hash(user_data['password_hash'], password):
        return None, 'Invalid username or password'

    if not user_data.get('is_active', 1):
        return None, 'This account is disabled'

    user_data.pop('password_hash', None)
    return user_data, None


def get_auth_serializer():
    secret_key = os.getenv('SECRET_KEY', 'pothole_detection_secret_key_2024')
    return URLSafeTimedSerializer(secret_key, salt='pothole-auth-token')


def generate_auth_token(user_id, username=None):
    """Generate a signed auth token for cross-domain REST authentication."""
    s = get_auth_serializer()
    return s.dumps({'user_id': user_id, 'username': username})


def verify_auth_token(token, max_age=86400 * 30):
    """Verify and decode a signed auth token (valid for 30 days by default)."""
    if not token:
        return None
    s = get_auth_serializer()
    try:
        return s.loads(token, max_age=max_age)
    except (BadSignature, SignatureExpired, Exception):
        return None


def get_authenticated_user_id():
    """Extract authenticated user_id from session cookie or Authorization header."""
    # 1. Check Flask session cookie
    if 'user_id' in session and session['user_id']:
        return session['user_id']

    # 2. Check Authorization: Bearer <token> or X-Auth-Token header
    auth_header = request.headers.get('Authorization', '')
    token = None
    if auth_header.startswith('Bearer '):
        token = auth_header[7:].strip()
    elif request.headers.get('X-Auth-Token'):
        token = request.headers.get('X-Auth-Token').strip()
    elif request.args.get('token'):
        token = request.args.get('token').strip()

    if token:
        payload = verify_auth_token(token)
        if payload and 'user_id' in payload:
            session['user_id'] = payload['user_id']
            if payload.get('username'):
                session['username'] = payload['username']
            return payload['user_id']

    return None


def get_session_user():
    """Return the current authenticated user from Flask session or Authorization token."""
    user_id = get_authenticated_user_id()
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
        user_id = get_authenticated_user_id()
        if not user_id:
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
            return redirect(os.getenv('FRONTEND_URL', '/'))
        return f(*args, **kwargs)
    return decorated_function
