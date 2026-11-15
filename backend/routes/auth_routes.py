from flask import Blueprint, jsonify, request, redirect, url_for, session

from auth_utils import (
    USERS,
    create_user,
    get_session_user,
    verify_user_login,
)

bp = Blueprint('auth', __name__)


@bp.route('/register', methods=['POST'])
def register():
    """Register a new local user account."""
    data = request.get_json() or {}
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''
    email = (data.get('email') or '').strip()
    full_name = (data.get('full_name') or '').strip()

    if not username or not password:
        return jsonify({'success': False, 'error': 'Username and password are required'}), 400

    user, error = create_user(username, password, email=email, full_name=full_name, role='user')
    if error:
        return jsonify({'success': False, 'error': error}), 400

    session['user_id'] = user['id']
    session['username'] = user['username']
    session['email'] = user.get('email', '')
    session['full_name'] = user.get('full_name', user['username'])
    session['auth_method'] = 'local'
    session.permanent = True

    return jsonify({
        'success': True,
        'message': 'Registration successful',
        'user': {
            'id': user['id'],
            'username': user['username'],
            'email': user.get('email', ''),
            'full_name': user.get('full_name', user['username']),
            'role': user.get('role', 'user')
        }
    }), 201


@bp.route('/login', methods=['GET', 'POST'])
def login():
    frontend_url = os.getenv('FRONTEND_URL', 'https://pothole-detection-hfy3.vercel.app')
    if request.method == 'GET':
        if 'user_id' in session:
            if request.is_json or request.headers.get('Accept') == 'application/json':
                return jsonify({
                    'success': True,
                    'authenticated': True,
                    'user_id': session.get('user_id'),
                    'username': session.get('username'),
                    'full_name': session.get('full_name', session.get('username'))
                })
            return redirect(frontend_url)

        if request.is_json or request.headers.get('Accept') == 'application/json':
            return jsonify({'success': False, 'authenticated': False}), 401
        return redirect(frontend_url)

    data = request.get_json() or {}
    username = data.get('username', '').strip()
    password = data.get('password', '')

    if not username or not password:
        return jsonify({'success': False, 'error': 'Username and password are required'}), 400

    user, error = verify_user_login(username, password)
    if error:
        return jsonify({'success': False, 'error': error}), 401

    session['user_id'] = user['id']
    session['username'] = user['username']
    session['email'] = user.get('email', '')
    session['full_name'] = user.get('full_name', user['username'])
    session['auth_method'] = 'local'
    session.permanent = True

    return jsonify({
        'success': True,
        'message': 'Login successful',
        'user': {
            'id': user['id'],
            'username': user['username'],
            'email': user.get('email', ''),
            'full_name': user.get('full_name', user['username']),
            'role': user.get('role', 'user')
        }
    })


@bp.route('/logout', methods=['GET', 'POST'])
def logout():
    session.clear()
    frontend_url = os.getenv('FRONTEND_URL', 'https://pothole-detection-hfy3.vercel.app')
    if request.is_json or request.headers.get('Accept') == 'application/json' or request.method == 'POST':
        return jsonify({'success': True, 'message': 'Logged out successfully'})
    return redirect(frontend_url)


@bp.route('/api/session', methods=['GET'])
def session_info():
    """Return current session and user information."""
    user = get_session_user()
    if not user:
        return jsonify({'success': False, 'authenticated': False}), 401

    return jsonify({
        'success': True,
        'authenticated': True,
        'user': {
            'id': user['id'],
            'username': user['username'],
            'email': user.get('email', ''),
            'full_name': user.get('full_name', user['username']),
            'role': user.get('role', 'user')
        }
    })


@bp.route('/login-google')
def google_login():
    from app import google
    frontend_url = os.getenv('FRONTEND_URL', 'https://pothole-detection-hfy3.vercel.app')

    try:
        if google is None:
            return redirect(frontend_url)

        redirect_uri = url_for('auth.google_authorize', _external=True)
        return google.authorize_redirect(redirect_uri)
    except Exception:
        return redirect(frontend_url)


@bp.route('/authorize')
def google_authorize():
    from app import google
    frontend_url = os.getenv('FRONTEND_URL', 'https://pothole-detection-hfy3.vercel.app')

    try:
        if google is None:
            return redirect(frontend_url)

        token = google.authorize_access_token()
        user = token.get('userinfo')

        if not user or not user.get('email'):
            return redirect(frontend_url)

        session['user_id'] = user.get('email')
        session['username'] = user.get('name', 'User')
        session['email'] = user.get('email', '')
        session['full_name'] = user.get('name', 'User')
        session['picture'] = user.get('picture', '')
        session['auth_method'] = 'google'
        session.permanent = True

        return redirect(frontend_url)
    except Exception:
        return redirect(frontend_url)
