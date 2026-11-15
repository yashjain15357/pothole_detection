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

from flask import Flask, request, jsonify, send_file, send_from_directory, session, redirect, url_for
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

from config import APP_CONFIG, REACT_DIST_DIR, SUPPORTED_IMAGES, SUPPORTED_VIDEOS, configure_cors
from auth_utils import USERS, login_required, register_google_oauth
from report_utils import get_location_for_report, resolve_report_file, extract_location_from_text

try:
    from flask_cors import CORS
    has_cors = True
except ImportError:
    has_cors = False

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
from process import process_image, process_video, update_report_with_location, get_model, model

# Configure garbage collection for better memory usage
gc.set_threshold(500, 5, 5)

app = Flask(__name__)
for key, value in APP_CONFIG.items():
    app.config[key] = value

configure_cors(app)

# Simple user database for normal login (in production, use proper database)
# USERS is defined in auth_utils.py

# Initialize OAuth for Google authentication
oauth = OAuth(app)

# Register Google OAuth with non-committed credentials
google = register_google_oauth(oauth)

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
        print(f"Failed to load smtp_config.json: {e}")


def smtp_config_ready():
    """Check whether SMTP credentials are available in the environment or config file."""
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

# Register modular route blueprints
from routes.auth_routes import bp as auth_bp
from routes.detection_routes import bp as detection_bp
from routes.email_routes import bp as email_bp
from routes.report_routes import bp as report_bp
from routes.report_save import bp as report_save_bp

app.register_blueprint(auth_bp)
app.register_blueprint(detection_bp)
app.register_blueprint(email_bp)
app.register_blueprint(report_bp)
app.register_blueprint(report_save_bp)

# Routes
@app.route('/')
def home():
    react_index = REACT_DIST_DIR / 'index.html'
    if react_index.exists():
        return send_file(str(react_index))
    return jsonify({
        'status': 'online',
        'service': 'Fix My City - Pothole Detection API',
        'frontend_url': 'https://pothole-detection-hfy3.vercel.app',
        'health_check': '/api/health'
    }), 200


@app.route('/assets/<path:filename>')
def serve_assets(filename):
    candidates = [
        REACT_DIST_DIR / 'assets',
        Path(__file__).resolve().parent.parent / 'frontend' / 'dist' / 'assets',
        Path(__file__).resolve().parent / 'frontend' / 'dist' / 'assets',
    ]
    for c in candidates:
        if c.exists() and (c / filename).exists():
            return send_from_directory(str(c), filename)
    return jsonify({'error': f'Asset {filename} not found'}), 404


@app.route('/dashboard')
def dashboard():
    react_index = REACT_DIST_DIR / 'index.html'
    if react_index.exists():
        return send_file(str(react_index))
    return redirect('https://pothole-detection-hfy3.vercel.app')


@app.route('/api/user-info', methods=['GET'])
@login_required
def user_info():
    """Get current user information"""
    return jsonify({
        'username': session.get('username'),
        'user_id': session.get('user_id')
    }), 200


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
        from database import get_db_connection, is_postgres_db
        conn = get_db_connection()
        c = conn.cursor()

        if is_postgres_db():
            c.execute('SELECT COUNT(*) FROM reports')
            total_reports = c.fetchone()[0]

            c.execute('SELECT SUM(pothole_count) FROM reports WHERE pothole_count IS NOT NULL')
            total_potholes = c.fetchone()[0] or 0

            c.execute('SELECT report_type, COUNT(*) as count FROM reports GROUP BY report_type')
            by_type = {row[0]: row[1] for row in c.fetchall()}

            c.execute('''SELECT report_type, SUM(pothole_count) as total 
                         FROM reports WHERE pothole_count IS NOT NULL GROUP BY report_type''')
            potholes_by_type = {row[0]: row[1] or 0 for row in c.fetchall()}

            avg_potholes = {}
            for report_type in ['image', 'video', 'camera']:
                c.execute('''SELECT AVG(pothole_count) FROM reports 
                             WHERE report_type = %s AND pothole_count IS NOT NULL''', (report_type,))
                result = c.fetchone()[0]
                avg_potholes[report_type] = round(result, 2) if result else 0

            c.execute('''SELECT DATE(created_at) as date, COUNT(*) as count 
                         FROM reports WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'
                         GROUP BY DATE(created_at) ORDER BY date''')
            daily_reports = {row[0]: row[1] for row in c.fetchall()}

            c.execute('''SELECT id, report_type, filename, pothole_count, created_at 
                         FROM reports WHERE pothole_count IS NOT NULL 
                         ORDER BY pothole_count DESC LIMIT 10''')
            top_reports = [{'id': row[0], 'type': row[1], 'name': row[2] or f'Report_{row[0]}',
                           'count': row[3], 'date': row[4]} for row in c.fetchall()]
        else:
            c.execute('SELECT COUNT(*) FROM reports')
            total_reports = c.fetchone()[0]

            c.execute('SELECT SUM(pothole_count) FROM reports WHERE pothole_count IS NOT NULL')
            total_potholes = c.fetchone()[0] or 0

            c.execute('SELECT report_type, COUNT(*) as count FROM reports GROUP BY report_type')
            by_type = {row[0]: row[1] for row in c.fetchall()}

            c.execute('''SELECT report_type, SUM(pothole_count) as total 
                         FROM reports WHERE pothole_count IS NOT NULL GROUP BY report_type''')
            potholes_by_type = {row[0]: row[1] or 0 for row in c.fetchall()}

            avg_potholes = {}
            for report_type in ['image', 'video', 'camera']:
                c.execute('''SELECT AVG(pothole_count) FROM reports 
                             WHERE report_type = ? AND pothole_count IS NOT NULL''', (report_type,))
                result = c.fetchone()[0]
                avg_potholes[report_type] = round(result, 2) if result else 0

            c.execute('''SELECT DATE(created_at) as date, COUNT(*) as count 
                         FROM reports WHERE created_at >= datetime('now', '-7 days')
                         GROUP BY DATE(created_at) ORDER BY date''')
            daily_reports = {row[0]: row[1] for row in c.fetchall()}

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
        from database import get_db_connection, is_postgres_db

        report_type = request.args.get('type')
        min_potholes = request.args.get('min_potholes', type=int)
        max_potholes = request.args.get('max_potholes', type=int)
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        sort_by = request.args.get('sort_by', 'created_at')
        order = request.args.get('order', 'DESC')
        limit = request.args.get('limit', 50, type=int)

        if sort_by not in ['created_at', 'pothole_count']:
            sort_by = 'created_at'

        conn = get_db_connection()
        c = conn.cursor()

        query = '''SELECT id, report_type, filename, pothole_count, unique_potholes, 
                          runtime_seconds, created_at, latitude, longitude, report_path FROM reports WHERE 1=1'''
        params = []

        if report_type:
            if is_postgres_db():
                query += ' AND report_type = %s'
            else:
                query += ' AND report_type = ?'
            params.append(report_type)

        if min_potholes is not None:
            if is_postgres_db():
                query += ' AND pothole_count >= %s'
            else:
                query += ' AND pothole_count >= ?'
            params.append(min_potholes)

        if max_potholes is not None:
            if is_postgres_db():
                query += ' AND pothole_count <= %s'
            else:
                query += ' AND pothole_count <= ?'
            params.append(max_potholes)

        if date_from:
            if is_postgres_db():
                query += ' AND DATE(created_at) >= %s'
            else:
                query += ' AND DATE(created_at) >= ?'
            params.append(date_from)

        if date_to:
            if is_postgres_db():
                query += ' AND DATE(created_at) <= %s'
            else:
                query += ' AND DATE(created_at) <= ?'
            params.append(date_to)

        query += f' ORDER BY {sort_by} {order} LIMIT %s' if is_postgres_db() else f' ORDER BY {sort_by} {order} LIMIT ?'
        params.append(limit)

        c.execute(query, params)
        rows = c.fetchall()
        conn.close()

        reports = []
        for row in rows:
            reports.append({
                'id': row[0],
                'type': row[1],
                'report_type': row[1],
                'name': row[2] or f'Report_{row[0]}',
                'filename': row[2] or f'Report_{row[0]}',
                'pothole_count': row[3],
                'unique_potholes': row[4],
                'runtime': row[5],
                'created_at': row[6],
                'latitude': row[7],
                'longitude': row[8],
                'path': row[9]
            })

        return jsonify({
            'success': True,
            'data': reports,
            'count': len(reports)
        }), 200
    except Exception as e:
        print(f"Error filtering reports: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/report/<path:report_path>')
@login_required
def get_report(report_path):
    """Get report content"""
    try:
        # Convert forward slashes to backslashes for Windows compatibility
        report_path = report_path.replace('/', '\\')
        file_path = Path(report_path)
        
        print(f"Attempting to read report: {file_path}")
        
        if not file_path.exists():
            print(f"File not found: {file_path}")
            return jsonify({'error': f'Report not found: {file_path}'}), 404
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        print(f"Report loaded successfully")
        return jsonify({'content': content}), 200
    except Exception as e:
        print(f"Error loading report: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/report-by-id/<int:report_id>')
@login_required
def get_report_by_id_route(report_id):
    """Get report content by ID from database or file storage"""
    try:
        report = get_report_by_id(report_id)
        
        if not report:
            return jsonify({'success': False, 'error': f'Report #{report_id} not found in database'}), 404
        
        report_text = None
        
        # 1. Try fetching stored file blob from database
        try:
            file_entry = get_report_file(report_id)
            if file_entry and file_entry.get('content'):
                c = file_entry['content']
                if isinstance(c, bytes):
                    report_text = c.decode('utf-8', errors='replace')
                else:
                    report_text = str(c)
        except Exception as e:
            print(f"Error fetching blob for report {report_id}: {e}")

        # 2. Try resolving the file on disk
        if not report_text and report.get('path'):
            file_path = resolve_report_file(report['path'])
            if file_path and file_path.exists():
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        report_text = f.read()
                except Exception as e:
                    print(f"Error reading report file on disk: {e}")

        # 3. Fallback: dynamically generate clean report summary from SQLite database
        if not report_text:
            lat_str = f"{float(report['latitude']):.6f}" if report.get('latitude') else "Not Geotagged"
            lng_str = f"{float(report['longitude']):.6f}" if report.get('longitude') else "Not Geotagged"
            report_text = f"""============================================================
POTHOLE DETECTION REPORT #{report_id}
============================================================
Report Type: {str(report.get('report_type', 'N/A')).upper()}
Source:      {report.get('name') or report.get('filename') or 'Live Inspection'}
Date/Time:   {report.get('timestamp') or report.get('created_at') or 'N/A'}
Logged At:   {report.get('created_at', 'N/A')}

DETECTION SUMMARY
------------------------------------------------------------
Total Detections: {report.get('pothole_count', 0)}
Unique Potholes:  {report.get('unique_potholes', report.get('pothole_count', 0))}
"""
            if report.get('runtime'):
                report_text += f"Runtime Duration: {report.get('runtime')} seconds\n"
            
            report_text += f"""
ROAD LOCATION
------------------------------------------------------------
Latitude:  {lat_str}
Longitude: {lng_str}
============================================================
"""

        return jsonify({'success': True, 'content': report_text}), 200
    except Exception as e:
        print(f"Error loading report by ID: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/download-report/<path:report_path>')
@login_required
def download_report(report_path):
    """Download a report from disk, with compatibility fallbacks for older Flask versions."""
    # Log incoming request info for debugging
    try:
        print(f"Raw download request - report_path param: {report_path}")
        print(f"Request URL: {request.url}")
        print(f"Full path: {request.full_path}")
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
    print(f"Download requested: {file_path} (size={size})")

    if size == 0:
        print("Report file size is 0 bytes — returning error instead of empty download")
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
                p = resolve_report_file(report.get('path'))
                if p and p.exists():
                    with open(p, 'r', encoding='utf-8') as f:
                        report_text = f.read()
            except Exception as e:
                print(f"Failed to read report file from disk: {e}")

        if not report_text:
            return jsonify({'error': 'No report content available to generate PDF'}), 404

        # Ensure location appears in PDF when available from any report source.
        location = get_location_for_report(report, report_text)
        if location and not re.search(r'Latitude\s*:', report_text, re.IGNORECASE):
            report_text = (
                "LOCATION\n"
                f"Latitude: {location['latitude']:.6f}\n"
                f"Longitude: {location['longitude']:.6f}\n"
                + ("-" * 60) + "\n\n"
                + report_text
            )

        # Generate PDF in-memory using reportlab if available
        try:
            from io import BytesIO
            try:
                from reportlab.pdfgen import canvas
                from reportlab.lib.pagesizes import letter
            except Exception as e:
                print('reportlab not installed:', e)
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
            print(f"PDF generation error: {e}")
            return jsonify({'error': str(e)}), 500

    except Exception as e:
        print(f"Error in download_report_pdf: {e}")
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
@app.route('/api/health')
def health():
    """Health check endpoint"""
    yolo_model = get_model()
    return jsonify({
        'status': 'healthy',
        'model_loaded': yolo_model is not None,
        'timestamp': datetime.now().isoformat()
    }), 200


@app.route('/detect-frame', methods=['POST'])
@login_required
def detect_frame():
    """Process a single frame for camera detection"""
    yolo_model = get_model()
    if yolo_model is None:
        return jsonify({'success': False, 'error': 'Model not loaded'}), 500
    
    try:
        data = request.json or {}
        if 'image' not in data:
            return jsonify({'success': False, 'error': 'No image data'}), 400
        
        try:
            # Decode base64 image - handle both data URI and raw base64
            image_str = data['image']
            
            # Remove data URI prefix if present
            if image_str.startswith('data:'):
                if ',' in image_str:
                    image_str = image_str.split(',', 1)[1]
                else:
                    return jsonify({'success': False, 'error': 'Invalid data URI format'}), 400
            
            # Validate that we have actual data
            if not image_str or len(image_str) < 50:
                return jsonify({'success': False, 'error': 'Image data is too small'}), 400
            
            # Decode base64
            try:
                img_bytes = base64.b64decode(image_str)
            except Exception as b64_error:
                return jsonify({'success': False, 'error': f'Invalid base64 format: {b64_error}'}), 400
            
            if not img_bytes:
                return jsonify({'success': False, 'error': 'Decoded image is empty'}), 400
            
            # Convert to numpy array and decode image
            nparr = np.frombuffer(img_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if img is None:
                return jsonify({'success': False, 'error': 'Failed to decode JPEG data'}), 400
        except Exception as decode_error:
            return jsonify({'success': False, 'error': f'Image decode error: {str(decode_error)}'}), 400
        
        # Perform detection with model
        try:
            orig_h, orig_w = img.shape[:2]
            results = yolo_model.predict(
                source=img, 
                conf=0.25,
                imgsz=416,
                verbose=False,
                device='cpu'
            )
            if not results:
                return jsonify({'success': False, 'error': 'Model prediction failed'}), 500
            
            result = results[0]
            pothole_count = len(result.boxes) if result.boxes is not None else 0
            
            pothole_ids = []
            boxes = []
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
                    for prev_id, prev_centroid in camera_session.get('previous_centroids', {}).items():
                        distance = np.sqrt((cx - prev_centroid[0])**2 + (cy - prev_centroid[1])**2)
                        if distance < camera_session.get('distance_threshold', 50):
                            pothole_id = prev_id
                            break
                    
                    # If no match found, assign new ID
                    if pothole_id is None:
                        pothole_id = camera_session.get('next_pothole_id', 1)
                        camera_session['next_pothole_id'] = pothole_id + 1
                    
                    camera_session['unique_pothole_ids'].add(pothole_id)
                    pothole_ids.append(pothole_id)
                    
                    boxes.append({
                        'id': pothole_id,
                        'pothole_id': pothole_id,
                        'x1': int(x1),
                        'y1': int(y1),
                        'x2': int(x2),
                        'y2': int(y2),
                        'orig_width': orig_w,
                        'orig_height': orig_h,
                        'confidence': f"{conf:.2%}"
                    })
                
                camera_session['previous_centroids'] = current_centroids
            else:
                camera_session['previous_centroids'] = {}
            
            unique_total = len(camera_session.get('unique_pothole_ids', set()))
            
            del result, results, img, nparr, img_bytes
            gc.collect()
            
            return jsonify({
                'success': True,
                'pothole_count': pothole_count,
                'potholes_count': pothole_count,
                'pothole_ids': pothole_ids,
                'unique_count': unique_total,
                'unique_potholes_count': unique_total,
                'boxes': boxes
            }), 200
        except Exception as model_error:
            gc.collect()
            return jsonify({'success': False, 'error': f'Detection error: {str(model_error)}'}), 500
    
    except Exception as e:
        print(f"General error in /detect-frame: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': f'Server error: {str(e)}'}), 500


@app.route('/api/smtp-config', methods=['GET', 'POST'])
@login_required
def smtp_config_api():
    """Get or update SMTP credentials"""
    global SMTP_SERVER, SMTP_PORT, SMTP_EMAIL, SMTP_APP_PASSWORD, SMTP_USE_STARTTLS
    config_file = Path('smtp_config.json')
    if request.method == 'GET':
        email = SMTP_EMAIL
        configured = bool(SMTP_EMAIL and SMTP_APP_PASSWORD)
        return jsonify({
            'success': True,
            'smtp_email': email,
            'configured': configured,
            'smtp_server': SMTP_SERVER,
            'smtp_port': SMTP_PORT
        }), 200
    
    # POST - update credentials
    data = request.get_json() or {}
    email = data.get('smtp_email', '').strip()
    password = data.get('smtp_app_password', '').strip().replace(' ', '')
    server = data.get('smtp_server', 'smtp.gmail.com').strip()
    port = int(data.get('smtp_port', 587))
    
    if not email or not password:
        return jsonify({'success': False, 'error': 'SMTP Email and App Password are required'}), 400
    
    config = {
        'SMTP_SERVER': server,
        'SMTP_PORT': port,
        'SMTP_EMAIL': email,
        'SMTP_APP_PASSWORD': password,
        'SMTP_USE_STARTTLS': True
    }
    
    try:
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)
        
        SMTP_SERVER = server
        SMTP_PORT = port
        SMTP_EMAIL = email
        SMTP_APP_PASSWORD = password
        SMTP_USE_STARTTLS = True
        
        return jsonify({'success': True, 'message': 'SMTP configuration saved successfully!'}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/send-report-email', methods=['POST'])
@login_required
def send_report_email():
    """Send a saved report file by SMTP email attachment."""
    try:
        data = request.get_json() or {}
        report_id = data.get('report_id')
        report_path_raw = data.get('report_path', '')
        report_name = data.get('report_name', 'report')
        recipient_email = data.get('recipient_email', '').strip()
        message = data.get('message', '')
        
        # Validate inputs
        if not recipient_email:
            return jsonify({'success': False, 'error': 'Recipient email is required'}), 400
        
        # Resolve file or create temporary attachment from database
        file_path = resolve_report_file(report_path_raw) if report_path_raw else None
        temp_file_to_clean = None
        
        if not file_path or not file_path.exists():
            report_text = None
            if report_id:
                try:
                    file_entry = get_report_file(report_id)
                    if file_entry and file_entry.get('content'):
                        c = file_entry['content']
                        report_text = c.decode('utf-8', errors='replace') if isinstance(c, bytes) else str(c)
                except Exception:
                    pass
                if not report_text:
                    r_item = get_report_by_id(report_id)
                    if r_item:
                        lat_val = f"{float(r_item['latitude']):.6f}" if r_item.get('latitude') else "Not Geotagged"
                        lng_val = f"{float(r_item['longitude']):.6f}" if r_item.get('longitude') else "Not Geotagged"
                        report_text = f"""============================================================
POTHOLE DETECTION REPORT #{report_id}
============================================================
Report Type: {r_item.get('report_type', 'N/A').upper()}
Source:      {r_item.get('name') or r_item.get('filename') or 'Inspection'}
Date/Time:   {r_item.get('timestamp') or r_item.get('created_at')}
Potholes:    {r_item.get('pothole_count', 0)}
Location:    Latitude {lat_val}, Longitude {lng_val}
============================================================
"""
            if not report_text:
                report_text = f"Pothole Detection Report - {report_name}\nSent on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"

            import tempfile
            tf = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', prefix=f"pothole_report_{report_id or 'export'}_", delete=False, encoding='utf-8')
            tf.write(report_text)
            tf.close()
            file_path = Path(tf.name)
            temp_file_to_clean = file_path

        report_name = report_name or file_path.name

        if not smtp_config_ready():
            return jsonify({
                'success': False,
                'error': 'SMTP is not configured. Please configure your email & Google App Password in Settings or smtp_config.json.'
            }), 400

        if '@' in SMTP_SERVER or '.' not in SMTP_SERVER:
            return jsonify({
                'success': False,
                'error': f'Invalid SMTP server configured: {SMTP_SERVER}. Use smtp.gmail.com for Gmail.'
            }), 400
        
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
                    <h2 style="color: #4f46e5;">🛣️ FIX MY CITY - Pothole Detection Report</h2>
                    <p>Dear Authority / User,</p>
                    <p>Please find attached the official road hazard report: <strong>{report_name}</strong></p>
                    
                    {f'<p><strong>Message from sender:</strong></p><p style="background: #f8fafc; padding: 12px; border-left: 4px solid #4f46e5; border-radius: 4px;">{message}</p>' if message else ''}
                    
                    <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;">
                    
                    <p><strong>Report Summary:</strong></p>
                    <ul>
                        <li>Report ID: #{report_id or 'N/A'}</li>
                        <li>Report Name: {report_name}</li>
                        <li>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</li>
                        <li>Dispatched by: Pothole Detection AI Platform</li>
                    </ul>
                    
                    <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;">
                    
                    <p style="font-size: 12px; color: #64748b;">
                        This automated notification was generated by FIX MY CITY Road Inspection System.
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
                
                print(f"Email sent successfully to {recipient_email}")
                return jsonify({
                    'success': True,
                    'message': f'Report sent successfully to {recipient_email}'
                }), 200
                
            except smtplib.SMTPAuthenticationError:
                return jsonify({
                    'success': False,
                    'error': 'Gmail authentication failed: Invalid Google App Password. Please generate a 16-character App Password at myaccount.google.com/apppasswords'
                }), 400
            except Exception as error:
                print(f"SMTP error: {error}")
                return jsonify({
                    'success': False,
                    'error': f'Failed to send email via SMTP: {str(error)}'
                }), 500
        
        except Exception as e:
            print(f"Error sending email: {e}")
            return jsonify({'success': False, 'error': f'Failed to send email: {str(e)}'}), 500
        finally:
            if temp_file_to_clean and temp_file_to_clean.exists():
                try:
                    os.unlink(str(temp_file_to_clean))
                except Exception:
                    pass
    
    except Exception as e:
        print(f"Error processing email request: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


if __name__ == '__main__':
    # Initialize database on startup
    init_database()
    app.run(debug=False, use_reloader=False, host='0.0.0.0', port=5000)
