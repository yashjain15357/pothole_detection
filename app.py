# Flask Application for Pothole Detection System
import os
import gc
import sys

# Set YOLO config directory before importing YOLO
os.environ['YOLO_CONFIG_DIR'] = '/tmp/Ultralytics'
os.environ['YOLO_CACHE'] = '/tmp/yolo_cache'
os.environ['ULTRALYTICS_SKIP_UPDATE'] = 'true'

# Optimization: Set memory optimization flags
os.environ['PYTHONUNBUFFERED'] = '1'

from flask import Flask, render_template, request, jsonify, send_file, session, redirect, url_for
from pathlib import Path
import cv2
import numpy as np
from datetime import datetime, timedelta
from ultralytics import YOLO
import json
import base64
from io import BytesIO
import re
import threading
import smtplib
import ssl
import torch
from functools import wraps
import mimetypes
from urllib.parse import urlencode
from authlib.integrations.flask_client import OAuth

# Import database functions
from database import (
    init_database,
    save_report_to_db,
    save_report_file,
    get_reports_from_db,
    get_database_stats,
    get_report_by_id,
    get_report_file
)

# Import process functions from process module
from process import process_image, process_video, update_report_with_location, model

# Configure garbage collection for better memory usage
gc.set_threshold(500, 5, 5)

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max file size
app.config['SECRET_KEY'] = 'pothole_detection_secret_key_2024'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)

# Simple user database for normal login (in production, use proper database)
USERS = {
    'admin': 'admin123',
    'user': 'user123',
    'demo': 'demo123'
}

# Initialize OAuth for Google authentication
oauth = OAuth(app)

def load_google_oauth_credentials():
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
            print(f"❌ Failed to load Google OAuth credentials from file: {error}")

    return client_id, client_secret


def register_google_oauth():
    client_id, client_secret = load_google_oauth_credentials()

    if not client_id or not client_secret:
        print(
            "⚠️ Google OAuth is not configured. Set GOOGLE_CLIENT_ID and "
            "GOOGLE_CLIENT_SECRET or add an ignored google_oauth_credentials.json file."
        )
        return None

    return oauth.register(
        name='google',
        client_id=client_id,
        client_secret=client_secret,
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        client_kwargs={
            'scope': 'openid email profile'
        }
    )


# Register Google OAuth with non-committed credentials
google = register_google_oauth()

# Configure garbage collection for better memory usage
gc.set_threshold(500, 5, 5)

# SMTP email configuration
SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
SMTP_EMAIL = os.getenv('SMTP_EMAIL', '').strip()
SMTP_APP_PASSWORD = os.getenv('SMTP_APP_PASSWORD', '').strip()
SMTP_USE_STARTTLS = os.getenv('SMTP_USE_STARTTLS', 'true').lower() in ('1', 'true', 'yes')


def load_smtp_config_from_file():
    config_file = Path('smtp_config.json')
    if not config_file.exists():
        return

    try:
        with open(config_file, 'r', encoding='utf-8') as file:
            config = json.load(file)

        global SMTP_SERVER, SMTP_PORT, SMTP_EMAIL, SMTP_APP_PASSWORD, SMTP_USE_STARTTLS
        loaded_server = str(config.get('SMTP_SERVER', SMTP_SERVER)).strip()
        if loaded_server and '@' not in loaded_server:
            SMTP_SERVER = loaded_server
        SMTP_PORT = int(config.get('SMTP_PORT', SMTP_PORT))
        SMTP_EMAIL = str(config.get('SMTP_EMAIL', SMTP_EMAIL)).strip() or SMTP_EMAIL
        SMTP_APP_PASSWORD = str(config.get('SMTP_APP_PASSWORD', SMTP_APP_PASSWORD)).strip() or SMTP_APP_PASSWORD
        SMTP_USE_STARTTLS = bool(config.get('SMTP_USE_STARTTLS', SMTP_USE_STARTTLS))
    except Exception as e:
        print(f"❌ Failed to load smtp_config.json: {e}")


def smtp_config_ready():
    if SMTP_EMAIL and SMTP_APP_PASSWORD:
        return True

    load_smtp_config_from_file()
    return bool(SMTP_EMAIL and SMTP_APP_PASSWORD)

# Global camera session tracker - tracks potholes across frames
camera_session = {
    'active': False,
    'previous_centroids': {},
    'next_pothole_id': 1,
    'unique_pothole_ids': set(),
    'distance_threshold': 50
}

# Define supported file extensions
SUPPORTED_IMAGES = ('.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff')
SUPPORTED_VIDEOS = ('.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv')



# Authentication decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def resolve_report_file(report_path: str):
    """Resolve a report file path safely on Windows and recover from escaped paths."""
    if not report_path:
        return None

    cleaned_path = str(report_path).strip().strip('"').strip("'")
    cleaned_path = cleaned_path.replace('\t', '').replace('\n', '').replace('\r', '').replace('\x0b', '').replace('\x0c', '')
    cleaned_path = cleaned_path.replace(chr(92), '/')

    candidate = Path(cleaned_path)
    if candidate.exists():
        return candidate

    filename = candidate.name or cleaned_path.split('/')[-1]
    search_roots = [
        Path.cwd(),
        Path('IN_image'),
        Path('IN_image/locations'),
        Path('IN_vedio'),
        Path('IN_vedio/locations'),
        Path('IN_cam'),
    ]

    for root in search_roots:
        if not root.exists():
            continue
        try:
            for file_path in root.rglob('*'):
                if file_path.is_file() and (file_path.name == filename or filename in file_path.name):
                    return file_path
        except Exception:
            continue

    return None


# Routes
@app.route('/')
def home():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('login.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        # Check if user is already logged in
        if 'user_id' in session:
            return redirect(url_for('dashboard'))
        return render_template('login.html')
    
    # POST request - handle normal login
    data = request.get_json() or {}
    username = data.get('username', '').strip()
    password = data.get('password', '')
    
    if not username or not password:
        return jsonify({'success': False, 'error': 'Username and password are required'}), 400
    
    # Check credentials
    if username in USERS and USERS[username] == password:
        session['user_id'] = username
        session['username'] = username
        session['auth_method'] = 'normal'
        session.permanent = True
        return jsonify({'success': True, 'message': 'Login successful'})
    
    return jsonify({'success': False, 'error': 'Invalid username or password'}), 401


@app.route('/login-google')
def google_login():
    """Redirect user to Google OAuth login page"""
    try:
        if google is None:
            print("❌ Google OAuth is not configured")
            return redirect(url_for('login'))

        # Use exact redirect URI that matches Google Cloud Console
        redirect_uri = url_for('google_authorize', _external=True)
        print(f"🔗 Redirecting to Google with URI: {redirect_uri}")
        return google.authorize_redirect(redirect_uri)
    except Exception as e:
        print(f"❌ Error in google_login: {e}")
        return redirect(url_for('login'))


@app.route('/authorize')
def google_authorize():
    """Google OAuth callback handler"""
    try:
        if google is None:
            print("❌ Google OAuth is not configured")
            return redirect(url_for('login'))

        print("📍 Callback received from Google")
        
        # Get the authorization token
        token = google.authorize_access_token()
        print(f"✓ Token received")
        
        # Extract user info
        user = token.get('userinfo')
        print(f"📦 User info: {user}")
        
        if not user or not user.get('email'):
            print("❌ No user info received")
            return redirect(url_for('login'))
        
        # Store user info in session
        session['user_id'] = user.get('email')
        session['username'] = user.get('name', 'User')
        session['email'] = user.get('email', '')
        session['picture'] = user.get('picture', '')
        session['auth_method'] = 'google'
        session.permanent = True
        
        print(f"✓ User logged in via Google: {user.get('email')}")
        print(f"✓ Redirecting to dashboard")
        
        return redirect(url_for('dashboard'))
    
    except Exception as e:
        print(f"❌ Google OAuth error: {e}")
        import traceback
        traceback.print_exc()
        return redirect(url_for('login'))


@app.route('/logout', methods=['GET', 'POST'])
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('index.html')


@app.route('/')
def index():
    # Redirect to login if not authenticated, otherwise to dashboard
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/upload-image', methods=['POST'])
@login_required
def upload_image():
    """Upload and process image from device"""
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'No file selected'}), 400
    
    if not file.filename.lower().endswith(SUPPORTED_IMAGES):
        return jsonify({'success': False, 'error': 'Invalid file type. Please upload an image.'}), 400
    
    try:
        # Save to temp location
        temp_dir = Path('/tmp/pothole_uploads')  # Use /tmp for Render compatibility
        temp_dir.mkdir(exist_ok=True, parents=True)
        filepath = temp_dir / file.filename
        file.save(str(filepath))
        
        result, error = process_image(str(filepath))
        
        if error:
            return jsonify({'success': False, 'error': error}), 500
        
        # Add location if provided (from camera capture)
        latitude = request.form.get('latitude')
        longitude = request.form.get('longitude')
        
        if latitude and longitude:
            try:
                result['report']['location'] = {
                    'latitude': float(latitude),
                    'longitude': float(longitude)
                }
                # Update report files with location
                update_report_with_location(result['report'], float(latitude), float(longitude))
            except (ValueError, TypeError):
                pass  # Location data invalid, ignore
        
        return jsonify(result), 200
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/upload-video', methods=['POST'])
@login_required
def upload_video():
    """Upload and process video from device"""
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'No file selected'}), 400
    
    if not file.filename.lower().endswith(SUPPORTED_VIDEOS):
        return jsonify({'success': False, 'error': 'Invalid file type. Please upload a video.'}), 400
    
    try:
        # Save to temp location
        temp_dir = Path('/tmp/pothole_uploads')  # Use /tmp for Render compatibility
        temp_dir.mkdir(exist_ok=True, parents=True)
        filepath = temp_dir / file.filename
        file.save(str(filepath))
        
        result, error = process_video(str(filepath))
        
        if error:
            return jsonify({'success': False, 'error': error}), 500
        
        return jsonify(result), 200
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/reports')
@login_required
def reports():
    """Get list of all reports from database"""
    # Fetch reports from database
    reports_data = get_reports_from_db()
    
    return jsonify(reports_data), 200


@app.route('/reports-stats')
@login_required
def reports_stats():
    """Get database statistics"""
    stats = get_database_stats()
    return jsonify(stats), 200


@app.route('/api/dashboard/analytics', methods=['GET'])
@login_required
def dashboard_analytics():
    """Get comprehensive analytics for dashboard"""
    try:
        from database import sqlite3, DATABASE
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        
        # Total statistics
        c.execute('SELECT COUNT(*) FROM reports')
        total_reports = c.fetchone()[0]
        
        c.execute('SELECT SUM(pothole_count) FROM reports WHERE pothole_count IS NOT NULL')
        total_potholes = c.fetchone()[0] or 0
        
        # By report type
        c.execute('SELECT report_type, COUNT(*) as count FROM reports GROUP BY report_type')
        by_type = {row[0]: row[1] for row in c.fetchall()}
        
        # Potholes by type
        c.execute('''SELECT report_type, SUM(pothole_count) as total 
                     FROM reports WHERE pothole_count IS NOT NULL GROUP BY report_type''')
        potholes_by_type = {row[0]: row[1] or 0 for row in c.fetchall()}
        
        # Average potholes per report type
        avg_potholes = {}
        for report_type in ['image', 'video', 'camera']:
            c.execute('''SELECT AVG(pothole_count) FROM reports 
                         WHERE report_type = ? AND pothole_count IS NOT NULL''', (report_type,))
            result = c.fetchone()[0]
            avg_potholes[report_type] = round(result, 2) if result else 0
        
        # Time-based analysis (last 7 days)
        from datetime import datetime, timedelta
        c.execute('''SELECT DATE(created_at) as date, COUNT(*) as count 
                     FROM reports WHERE created_at >= datetime('now', '-7 days')
                     GROUP BY DATE(created_at) ORDER BY date''')
        daily_reports = {row[0]: row[1] for row in c.fetchall()}
        
        # High pothole count reports (top 10)
        c.execute('''SELECT id, report_type, filename, pothole_count, created_at 
                     FROM reports WHERE pothole_count IS NOT NULL 
                     ORDER BY pothole_count DESC LIMIT 10''')
        top_reports = [{'id': row[0], 'type': row[1], 'name': row[2] or f'Report_{row[0]}', 
                       'count': row[3], 'date': row[4]} for row in c.fetchall()]
        
        conn.close()
        
        return jsonify({
            'success': True,
            'total_reports': total_reports,
            'total_potholes': total_potholes,
            'by_type': by_type,
            'potholes_by_type': potholes_by_type,
            'avg_potholes': avg_potholes,
            'daily_reports': daily_reports,
            'top_reports': top_reports
        }), 200
    except Exception as e:
        print(f"Error getting analytics: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/dashboard/reports-filtered', methods=['GET'])
@login_required
def get_filtered_reports():
    """Get filtered reports based on query parameters"""
    try:
        from database import sqlite3, DATABASE
        
        # Get filter parameters
        report_type = request.args.get('type')  # 'image', 'video', 'camera', or None for all
        min_potholes = request.args.get('min_potholes', type=int)
        max_potholes = request.args.get('max_potholes', type=int)
        date_from = request.args.get('date_from')  # YYYY-MM-DD
        date_to = request.args.get('date_to')      # YYYY-MM-DD
        sort_by = request.args.get('sort_by', 'created_at')  # created_at, pothole_count
        order = request.args.get('order', 'DESC')  # ASC or DESC
        limit = request.args.get('limit', 50, type=int)
        
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        
        # Build query
        query = '''SELECT id, report_type, filename, pothole_count, unique_potholes, 
                          runtime_seconds, created_at FROM reports WHERE 1=1'''
        params = []
        
        if report_type:
            query += ' AND report_type = ?'
            params.append(report_type)
        
        if min_potholes is not None:
            query += ' AND pothole_count >= ?'
            params.append(min_potholes)
        
        if max_potholes is not None:
            query += ' AND pothole_count <= ?'
            params.append(max_potholes)
        
        if date_from:
            query += ' AND DATE(created_at) >= ?'
            params.append(date_from)
        
        if date_to:
            query += ' AND DATE(created_at) <= ?'
            params.append(date_to)
        
        # Validate sort field
        if sort_by not in ['created_at', 'pothole_count']:
            sort_by = 'created_at'
        
        query += f' ORDER BY {sort_by} {order} LIMIT ?'
        params.append(limit)
        
        c.execute(query, params)
        rows = c.fetchall()
        
        reports = []
        for row in rows:
            reports.append({
                'id': row[0],
                'type': row[1],
                'name': row[2] or f'Report_{row[0]}',
                'pothole_count': row[3],
                'unique_potholes': row[4],
                'runtime': row[5],
                'created_at': row[6]
            })
        
        conn.close()
        
        return jsonify({
            'success': True,
            'count': len(reports),
            'reports': reports
        }), 200
    except Exception as e:
        print(f"Error getting filtered reports: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/report/<path:report_path>')
@login_required
def get_report(report_path):
    """Get report content"""
    try:
        # Convert forward slashes to backslashes for Windows compatibility
        report_path = report_path.replace('/', '\\')
        file_path = Path(report_path)
        
        print(f"📄 Attempting to read report: {file_path}")
        
        if not file_path.exists():
            print(f"❌ File not found: {file_path}")
            return jsonify({'error': f'Report not found: {file_path}'}), 404
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        print(f"✓ Report loaded successfully")
        return jsonify({'content': content}), 200
    except Exception as e:
        print(f"❌ Error loading report: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/report-by-id/<int:report_id>')
@login_required
def get_report_by_id_route(report_id):
    """Get report content by ID from database"""
    try:
        report = get_report_by_id(report_id)
        
        if not report:
            return jsonify({'error': 'Report not found'}), 404
        
        file_path = Path(report['path'])
        
        if not file_path.exists():
            return jsonify({'error': f'Report file not found: {report["path"]}'}), 404
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        return jsonify({'content': content}), 200
    except Exception as e:
        print(f"❌ Error loading report by ID: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/download-report/<path:report_path>')
@login_required
def download_report(report_path):
    """Download report file"""
    # Log incoming request info for debugging
    try:
        print(f"🔍 Raw download request - report_path param: {report_path}")
        print(f"🔍 Request URL: {request.url}")
        print(f"🔍 Full path: {request.full_path}")
    except Exception:
        pass

    file_path = resolve_report_file(report_path)
    if not file_path:
        return jsonify({'error': 'Report not found'}), 404

    download_name = file_path.name
    mimetype = 'text/plain' if file_path.suffix.lower() == '.txt' else 'application/octet-stream'

    # Log file info for debugging
    try:
        size = file_path.stat().st_size
    except Exception:
        size = None
    print(f"📥 Download requested: {file_path} (size={size})")

    if size == 0:
        print("⚠️ Report file size is 0 bytes — returning error instead of empty download")
        return jsonify({'error': 'Report file is empty'}), 500

    # Try modern Flask argument first, fall back to older name if needed
    try:
        return send_file(
            str(file_path),
            as_attachment=True,
            download_name=download_name,
            mimetype=mimetype
        )
    except TypeError:
        # Older Flask versions use 'attachment_filename'
        try:
            return send_file(
                str(file_path),
                as_attachment=True,
                attachment_filename=download_name,
                mimetype=mimetype
            )
        except Exception as e:
            # As a last-resort fallback, stream file bytes manually
            try:
                from flask import Response
                with open(file_path, 'rb') as f:
                    data = f.read()
                headers = {
                    'Content-Disposition': f'attachment; filename="{download_name}"',
                    'Content-Type': mimetype
                }
                return Response(data, headers=headers)
            except Exception as e2:
                print(f"❌ Fallback streaming failed: {e2}")
                return jsonify({'error': str(e)}), 500


@app.route('/download-report-pdf/<int:report_id>')
@login_required
def download_report_pdf(report_id):
    """Generate a PDF from stored report text (from DB) and send as attachment."""
    try:
        # Fetch report metadata
        report = get_report_by_id(report_id)
        if not report:
            return jsonify({'error': 'Report not found'}), 404

        # Try fetching stored file blob from DB
        file_entry = get_report_file(report_id)
        report_text = None
        if file_entry and file_entry.get('content'):
            try:
                # content may be bytes
                content = file_entry['content']
                if isinstance(content, bytes):
                    report_text = content.decode('utf-8', errors='replace')
                else:
                    report_text = str(content)
            except Exception:
                report_text = None

        # Fallback: try reading from filesystem path stored in report
        if not report_text and report.get('path'):
            try:
                p = Path(report.get('path'))
                if p.exists():
                    with open(p, 'r', encoding='utf-8') as f:
                        report_text = f.read()
            except Exception as e:
                print(f"❌ Failed to read report file from disk: {e}")

        if not report_text:
            return jsonify({'error': 'No report content available to generate PDF'}), 404

        # Generate PDF in-memory using reportlab if available
        try:
            from io import BytesIO
            try:
                from reportlab.pdfgen import canvas
                from reportlab.lib.pagesizes import letter
            except Exception as e:
                print('❌ reportlab not installed:', e)
                return jsonify({'error': 'PDF generation requires reportlab. Install with: pip install reportlab'}), 500

            buffer = BytesIO()
            c = canvas.Canvas(buffer, pagesize=letter)
            width, height = letter
            margin = 40
            y = height - margin
            line_height = 12

            # Draw title
            title = report.get('name') or f'Report_{report_id}'
            c.setFont('Helvetica-Bold', 14)
            c.drawString(margin, y, title)
            y -= (line_height * 2)

            c.setFont('Helvetica', 10)
            for raw_line in report_text.splitlines():
                # wrap long lines
                line = raw_line
                max_chars = 95
                while len(line) > 0:
                    chunk = line[:max_chars]
                    c.drawString(margin, y, chunk)
                    y -= line_height
                    line = line[max_chars:]
                    if y < margin + line_height:
                        c.showPage()
                        y = height - margin
                        c.setFont('Helvetica', 10)

            c.save()
            buffer.seek(0)

            download_name = f"{(report.get('name') or f'report_{report_id}').replace(' ', '_')}.pdf"
            try:
                return send_file(buffer, as_attachment=True, download_name=download_name, mimetype='application/pdf')
            except TypeError:
                return send_file(buffer, as_attachment=True, attachment_filename=download_name, mimetype='application/pdf')

        except Exception as e:
            print(f"❌ PDF generation error: {e}")
            return jsonify({'error': str(e)}), 500

    except Exception as e:
        print(f"❌ Error in download_report_pdf: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/start-camera-session', methods=['POST'])
@login_required
def start_camera_session():
    """Initialize camera tracking session"""
    global camera_session
    camera_session = {
        'active': True,
        'previous_centroids': {},
        'next_pothole_id': 1,
        'unique_pothole_ids': set(),
        'distance_threshold': 50
    }
    print("✓ Camera session started")
    return jsonify({'success': True, 'message': 'Camera session initialized'}), 200


@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'model_loaded': model is not None,
        'timestamp': datetime.now().isoformat()
    }), 200


@app.route('/api/user-info', methods=['GET'])
@login_required
def user_info():
    """Get current user information"""
    return jsonify({
        'username': session.get('username'),
        'user_id': session.get('user_id')
    }), 200


@app.route('/detect-frame', methods=['POST'])
@login_required
def detect_frame():
    """Process a single frame for camera detection"""
    if model is None:
        return jsonify({'success': False, 'error': 'Model not loaded'}), 500
    
    try:
        data = request.json
        if 'image' not in data:
            return jsonify({'success': False, 'error': 'No image data'}), 400
        
        try:
            # Decode base64 image - handle both data URI and raw base64
            image_str = data['image']
            
            print(f"📨 Received data (first 100 chars): {image_str[:100]}")
            
            # Remove data URI prefix if present
            if image_str.startswith('data:'):
                if ',' in image_str:
                    image_str = image_str.split(',', 1)[1]
                else:
                    print("❌ Invalid data URI format - no comma found")
                    return jsonify({'success': False, 'error': 'Invalid data URI format'}), 400
            
            # Validate that we have actual data
            if not image_str or len(image_str) == 0:
                print("❌ Base64 string is empty after split")
                return jsonify({'success': False, 'error': 'Base64 string is empty'}), 400
            
            print(f"✓ Base64 string length: {len(image_str)} characters")
            
            # Don't strip - it can remove important padding
            # But do validate length
            if len(image_str) < 50:
                print(f"❌ Base64 string too short: {len(image_str)} bytes")
                return jsonify({'success': False, 'error': 'Image data is too small'}), 400
            
            # Decode base64
            try:
                img_bytes = base64.b64decode(image_str)
            except Exception as b64_error:
                print(f"❌ Base64 decoding failed: {b64_error}")
                return jsonify({'success': False, 'error': 'Invalid base64 format'}), 400
            
            # Check if bytes are empty
            if not img_bytes or len(img_bytes) == 0:
                print("❌ Base64 decoded to empty bytes")
                return jsonify({'success': False, 'error': 'Decoded image is empty'}), 400
            
            print(f"✓ Base64 decoded: {len(img_bytes)} bytes")
            
            # Convert to numpy array and decode image
            nparr = np.frombuffer(img_bytes, np.uint8)
            if nparr.size == 0:
                print("❌ Numpy array is empty after frombuffer")
                return jsonify({'success': False, 'error': 'Image array is empty'}), 400
            
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if img is None:
                print(f"❌ cv2.imdecode failed - Image is None (array size: {nparr.size})")
                return jsonify({'success': False, 'error': 'Failed to decode JPEG data'}), 400
            
            print(f"✓ Image decoded successfully: shape={img.shape}")
        except Exception as decode_error:
            print(f"❌ Decode error: {decode_error}")
            import traceback
            traceback.print_exc()
            return jsonify({'success': False, 'error': f'Image decode error: {str(decode_error)}'}), 400
        
        # Perform detection with timeout and error handling
        try:
            results = model.predict(
                source=img, 
                conf=0.3,      # Increased confidence threshold for faster/cleaner detection
                imgsz=320,     # Further reduced from 416 for camera (smaller = faster)
                verbose=False,
                device=0 if torch.cuda.is_available() else 'cpu',
                half=False     # Disable half precision for accuracy
            )
            if not results or len(results) == 0:
                return jsonify({'success': False, 'error': 'Model prediction failed'}), 500
            
            result = results[0]
            pothole_count = len(result.boxes) if result.boxes is not None else 0
            
            pothole_ids = []
            boxes = []  # Store box coordinates
            current_centroids = {}
            
            if pothole_count > 0:
                for i, box in enumerate(result.boxes, 1):
                    x1, y1, x2, y2 = box.xyxy[0]
                    cx = (x1 + x2) / 2
                    cy = (y1 + y2) / 2
                    current_centroids[i] = (cx, cy)
                    conf = box.conf.item()
                    
                    # Match with previous centroids using spatial distance
                    pothole_id = None
                    for prev_id, prev_centroid in camera_session['previous_centroids'].items():
                        distance = np.sqrt((cx - prev_centroid[0])**2 + (cy - prev_centroid[1])**2)
                        if distance < camera_session['distance_threshold']:
                            pothole_id = prev_id
                            break
                    
                    # If no match found, assign new ID
                    if pothole_id is None:
                        pothole_id = camera_session['next_pothole_id']
                        camera_session['next_pothole_id'] += 1
                    
                    # Track unique pothole
                    camera_session['unique_pothole_ids'].add(pothole_id)
                    pothole_ids.append(pothole_id)
                    
                    boxes.append({
                        'id': pothole_id,
                        'x1': int(x1),
                        'y1': int(y1),
                        'x2': int(x2),
                        'y2': int(y2),
                        'confidence': f"{conf:.2%}"
                    })
                
                # Update previous centroids for next frame
                camera_session['previous_centroids'] = current_centroids
            else:
                # No detections, clear previous centroids
                camera_session['previous_centroids'] = {}
            
            print(f"✓ Detection complete: {pothole_count} detected, {len(camera_session['unique_pothole_ids'])} unique")
            
            # Clean up memory immediately
            del result, results, img, nparr, img_bytes
            
            # Aggressive garbage collection for camera frames (periodic)
            gc.collect()
            
            return jsonify({
                'success': True,
                'pothole_count': pothole_count,
                'pothole_ids': pothole_ids,
                'unique_count': len(camera_session['unique_pothole_ids']),
                'boxes': boxes  # Return box coordinates
            }), 200
        except Exception as model_error:
            print(f"❌ Model inference error: {model_error}")
            import traceback
            traceback.print_exc()
            gc.collect()
            return jsonify({'success': False, 'error': f'Detection error: {str(model_error)}'}), 500
    
    except Exception as e:
        print(f"❌ General error in /detect-frame: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': f'Server error: {str(e)}'}), 500


@app.route('/save-camera-report', methods=['POST'])
@login_required
def save_camera_report():
    """Save camera detection report"""
    try:
        data = request.json
        
        report_dir = Path("IN_cam")
        report_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Save JSON report
        report_file_json = report_dir / f"live_report_{timestamp}.json"
        with open(report_file_json, 'w', encoding='utf-8') as rf:
            json.dump(data, rf, indent=2)
        
        # Save TXT report
        report_file_txt = report_dir / f"live_report_{timestamp}.txt"
        with open(report_file_txt, 'w', encoding='utf-8') as rf:
            rf.write("LIVE CAMERA DETECTION - SHORT REPORT\n")
            rf.write("=" * 50 + "\n\n")
            rf.write(f"Timestamp: {data.get('timestamp', 'N/A')}\n")
            rf.write(f"Runtime: {data.get('runtime_seconds', 0)} seconds\n\n")
            rf.write("DETECTION SUMMARY\n")
            rf.write("-" * 50 + "\n")
            rf.write(f"Total Potholes Detected: {data.get('total_detections', 0)}\n")
            rf.write(f"Unique Potholes: {data.get('unique_potholes', 0)}\n")
            
            # Add pothole locations if available
            pothole_locations = data.get('pothole_locations', {})
            if pothole_locations:
                rf.write("\n" + "=" * 50 + "\n")
                rf.write("DETECTED POTHOLE LOCATIONS\n")
                rf.write("=" * 50 + "\n")
                for pothole_id, location_info in sorted(pothole_locations.items()):
                    rf.write(f"\nPothole {pothole_id}:\n")
                    rf.write(f"  Latitude:  {location_info.get('lat', 'N/A'):.6f}\n")
                    rf.write(f"  Longitude: {location_info.get('lng', 'N/A'):.6f}\n")
                    rf.write(f"  Time:      {location_info.get('timestamp', 'N/A')}\n")
            
            rf.write("\n" + "=" * 50 + "\n")
        
        # Save report to database and attach TXT content as blob
        report_id = save_report_to_db('camera', None, data, str(report_file_txt))
        try:
            if report_id:
                with open(report_file_txt, 'rb') as f:
                    content_bytes = f.read()
                save_report_file(report_id, report_file_txt.name, content_bytes, mime_type='text/plain')
        except Exception as e:
            print(f"⚠️ Failed to save report blob to DB: {e}")

        return jsonify({
            'success': True,
            'message': 'Report saved successfully',
            'report_file': str(report_file_txt),
            'report_id': report_id
        }), 200
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/save-location-with-report', methods=['POST'])
@login_required
def save_location_with_report():
    """Save location data with the detection report"""
    try:
        data = request.get_json()
        report = data.get('report', {})
        location = data.get('location', {})
        
        if not location:
            return jsonify({'success': False, 'error': 'No location data provided'}), 400
        
        # Find and update the most recent pothole report with location data
        report_dir = Path("IN_image")
        report_files = sorted(report_dir.glob("pothole_report_*.json"), reverse=True)
        
        if report_files:
            latest_report_file = report_files[0]
            
            # Read existing report
            with open(latest_report_file, 'r', encoding='utf-8') as f:
                existing_report = json.load(f)
            
            # Add location to the report
            existing_report['location'] = {
                'latitude': location.get('lat', 0),
                'longitude': location.get('lng', 0)
            }
            
            # Save updated report
            with open(latest_report_file, 'w', encoding='utf-8') as f:
                json.dump(existing_report, f, indent=2)
            
            # Also update the TXT file
            txt_file = latest_report_file.with_suffix('.txt').with_stem(latest_report_file.stem.replace('pothole_report', 'pothole_report'))
            txt_file = report_dir / f"{latest_report_file.stem.replace('pothole_report_', 'pothole_report_')}.txt"
            
            # Find corresponding TXT file
            txt_files = sorted(report_dir.glob("pothole_report_*.txt"), reverse=True)
            if txt_files:
                txt_file = txt_files[0]
                
                # Read existing TXT
                with open(txt_file, 'r', encoding='utf-8') as f:
                    txt_content = f.read()
                
                # Insert location information after filename
                import re
                pattern = r'(Image:.*?\n)'
                insertion = f'Latitude: {location.get("lat", 0):.6f}\nLongitude: {location.get("lng", 0):.6f}\n'
                txt_content = re.sub(pattern, r'\1' + insertion, txt_content)
                
                # Save updated TXT
                with open(txt_file, 'w', encoding='utf-8') as f:
                    f.write(txt_content)
        
        # Also create a location report file for reference
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        location_dir = Path("IN_image/locations")
        location_dir.mkdir(parents=True, exist_ok=True)
        
        # Save location with report details
        location_data = {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'filename': report.get('filename', 'unknown'),
            'latitude': location.get('lat', 0),
            'longitude': location.get('lng', 0),
            'pothole_count': report.get('pothole_count', 0),
            'detections': report.get('detections', [])
        }
        
        # Save as JSON
        location_file = location_dir / f"location_report_{timestamp}.json"
        with open(location_file, 'w', encoding='utf-8') as f:
            json.dump(location_data, f, indent=2)
        
        # Save as TXT for readability
        txt_file = location_dir / f"location_report_{timestamp}.txt"
        with open(txt_file, 'w', encoding='utf-8') as f:
            f.write("=" * 60 + "\n")
            f.write("POTHOLE DETECTION REPORT WITH LOCATION\n")
            f.write("=" * 60 + "\n")
            f.write(f"Timestamp: {location_data['timestamp']}\n")
            f.write(f"Image: {location_data['filename']}\n")
            f.write(f"Latitude: {location_data['latitude']:.6f}\n")
            f.write(f"Longitude: {location_data['longitude']:.6f}\n")
            f.write(f"Potholes Detected: {location_data['pothole_count']}\n")
            f.write("=" * 60 + "\n")
            
            if location_data['detections']:
                f.write("\nDetection Details:\n")
                f.write("-" * 60 + "\n")
                for det in location_data['detections']:
                    f.write(f"Pothole {det['pothole_id']}: Confidence = {det['confidence']}, Width = {det['width_px']}px, Height = {det['height_px']}px\n")
            else:
                f.write("\nNo potholes detected\n")
        
        return jsonify({'success': True, 'message': 'Location saved', 'location_file': str(location_file)}), 200
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/save-video-location-with-report', methods=['POST'])
@login_required
def save_video_location_with_report():
    """Save location data with the video detection report"""
    try:
        data = request.get_json()
        report = data.get('report', {})
        location = data.get('location', {})
        
        if not location:
            return jsonify({'success': False, 'error': 'No location data provided'}), 400
        
        # Find and update the most recent video report with location data
        report_dir = Path("IN_vedio")
        report_files = sorted(report_dir.glob("video_report_*.json"), reverse=True)
        
        if report_files:
            latest_report_file = report_files[0]
            
            # Read existing report
            with open(latest_report_file, 'r', encoding='utf-8') as f:
                existing_report = json.load(f)
            
            # Add location to the report
            existing_report['location'] = {
                'latitude': location.get('lat', 0),
                'longitude': location.get('lng', 0)
            }
            
            # Save updated report
            with open(latest_report_file, 'w', encoding='utf-8') as f:
                json.dump(existing_report, f, indent=2)
            
            # Also update the TXT file
            txt_files = sorted(report_dir.glob("video_report_*.txt"), reverse=True)
            if txt_files:
                txt_file = txt_files[0]
                
                # Read existing TXT
                with open(txt_file, 'r', encoding='utf-8') as f:
                    txt_content = f.read()
                
                # Insert location information after total frames
                pattern = r'(Total Frames:.*?\n)'
                insertion = f'Latitude: {location.get("lat", 0):.6f}\nLongitude: {location.get("lng", 0):.6f}\n'
                txt_content = re.sub(pattern, r'\1' + insertion, txt_content)
                
                # Save updated TXT
                with open(txt_file, 'w', encoding='utf-8') as f:
                    f.write(txt_content)
        
        # Also create a video location report file for reference
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        location_dir = Path("IN_vedio/locations")
        location_dir.mkdir(parents=True, exist_ok=True)
        
        # Save location with report details
        location_data = {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'filename': report.get('filename', 'unknown'),
            'latitude': location.get('lat', 0),
            'longitude': location.get('lng', 0),
            'total_frames': report.get('total_frames', 0),
            'total_potholes_detected': report.get('total_potholes_detected', 0),
            'unique_potholes': report.get('unique_potholes', 0)
        }
        
        # Save as JSON
        location_file = location_dir / f"video_location_report_{timestamp}.json"
        with open(location_file, 'w', encoding='utf-8') as f:
            json.dump(location_data, f, indent=2)
        
        # Save as TXT for readability
        txt_file = location_dir / f"video_location_report_{timestamp}.txt"
        with open(txt_file, 'w', encoding='utf-8') as f:
            f.write("=" * 60 + "\n")
            f.write("VIDEO DETECTION REPORT WITH LOCATION\n")
            f.write("=" * 60 + "\n")
            f.write(f"Timestamp: {location_data['timestamp']}\n")
            f.write(f"Video: {location_data['filename']}\n")
            f.write(f"Latitude: {location_data['latitude']:.6f}\n")
            f.write(f"Longitude: {location_data['longitude']:.6f}\n")
            f.write(f"Total Frames: {location_data['total_frames']}\n")
            f.write(f"Total Potholes Detected: {location_data['total_potholes_detected']}\n")
            f.write(f"Unique Potholes: {location_data['unique_potholes']}\n")
            f.write("=" * 60 + "\n")
        
        return jsonify({'success': True, 'message': 'Location saved', 'location_file': str(location_file)}), 200
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/send-report-email', methods=['POST'])
@login_required
def send_report_email():
    """Send report file via email using Gmail API"""
    try:
        data = request.get_json() or {}
        report_path_raw = data.get('report_path', '')
        report_name = data.get('report_name', 'report')
        recipient_email = data.get('recipient_email', '').strip()
        message = data.get('message', '')
        
        # Validate inputs
        if not recipient_email:
            return jsonify({'success': False, 'error': 'Recipient email is required'}), 400
        
        if not report_path_raw:
            return jsonify({'success': False, 'error': 'Report path is required'}), 400
        
        # Check if report file exists
        file_path = resolve_report_file(report_path_raw)
        if not file_path:
            return jsonify({'success': False, 'error': f'Report file not found: {report_path_raw}'}), 404

        report_name = report_name or file_path.name

        if not smtp_config_ready():
            return jsonify({
                'success': False,
                'error': 'SMTP is not configured. Set SMTP_EMAIL and SMTP_APP_PASSWORD environment variables.'
            }), 500

        if '@' in SMTP_SERVER or '.' not in SMTP_SERVER:
            return jsonify({
                'success': False,
                'error': f'Invalid SMTP server configured: {SMTP_SERVER}. Use smtp.gmail.com for Gmail.'
            }), 500
        
        try:
            # Create message with attachment
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            from email.mime.base import MIMEBase
            from email import encoders
            
            msg = MIMEMultipart()
            msg['to'] = recipient_email
            msg['subject'] = f'Pothole Detection Report - {report_name}'
            
            # Email body
            body = f"""
            <html>
                <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                    <h2 style="color: #667eea;">🛣️ Pothole Detection Report</h2>
                    <p>Dear User,</p>
                    <p>Please find attached the pothole detection report: <strong>{report_name}</strong></p>
                    
                    {f'<p><strong>Message from sender:</strong></p><p style="background: #f5f5f5; padding: 10px; border-left: 4px solid #667eea;">{message}</p>' if message else ''}
                    
                    <hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">
                    
                    <p><strong>Report Details:</strong></p>
                    <ul>
                        <li>Report Name: {report_name}</li>
                        <li>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</li>
                        <li>Sent by: Pothole Detection System</li>
                    </ul>
                    
                    <hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">
                    
                    <p style="font-size: 12px; color: #999;">
                        This is an automated email from the Pothole Detection System. 
                        Please do not reply to this email.
                    </p>
                </body>
            </html>
            """
            
            msg.attach(MIMEText(body, 'html'))
            
            # Attach file
            try:
                with open(file_path, 'rb') as attachment:
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(attachment.read())
                    encoders.encode_base64(part)
                    part.add_header('Content-Disposition', f'attachment; filename= {file_path.name}')
                    msg.attach(part)
            except Exception as e:
                return jsonify({'success': False, 'error': f'Failed to attach file: {str(e)}'}), 500
            
            # Send email via SMTP
            try:
                context = ssl.create_default_context()
                with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=30) as server:
                    if SMTP_USE_STARTTLS:
                        server.ehlo()
                        server.starttls(context=context)
                        server.ehlo()
                    server.login(SMTP_EMAIL, SMTP_APP_PASSWORD)
                    server.sendmail(SMTP_EMAIL, recipient_email, msg.as_string())
                
                print(f"✓ Email sent successfully to {recipient_email}")
                return jsonify({
                    'success': True,
                    'message': f'Report sent successfully to {recipient_email}'
                }), 200
                
            except Exception as error:
                print(f"❌ SMTP error: {error}")
                return jsonify({
                    'success': False,
                    'error': f'Failed to send email via SMTP: {str(error)}. Check SMTP server, username, and app password.'
                }), 500
        
        except Exception as e:
            print(f"❌ Error sending email: {e}")
            return jsonify({'success': False, 'error': f'Failed to send email: {str(e)}'}), 500
    
    except Exception as e:
        print(f"❌ Error processing email request: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


if __name__ == '__main__':
    # Initialize database on startup
    init_database()
    app.run(debug=True, host='0.0.0.0', port=5000)
