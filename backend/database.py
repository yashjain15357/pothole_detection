"""
Database Module for Pothole Detection System
Handles all database operations for storing and retrieving reports.
Supports SQLite for local/dev and PostgreSQL for Render/production via DATABASE_URL.
"""

import os
import sqlite3
from datetime import datetime
from pathlib import Path

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:  # pragma: no cover
    psycopg2 = None
    RealDictCursor = None

DATABASE_URL = os.getenv('DATABASE_URL', '').strip()

if DATABASE_URL:
    DATABASE = DATABASE_URL
    DB_ENGINE = 'postgres'
else:
    _db_dir = os.getenv('DATABASE_DIR', '')
    if _db_dir:
        Path(_db_dir).mkdir(parents=True, exist_ok=True)
        DATABASE = str(Path(_db_dir) / 'pothole_reports.db')
    else:
        DATABASE = 'pothole_reports.db'
    DB_ENGINE = 'sqlite'


def is_postgres_db():
    return DB_ENGINE == 'postgres'


def get_db_connection():
    """Return a DB connection for the active backend engine."""
    if is_postgres_db():
        if psycopg2 is None:
            raise RuntimeError('psycopg2 is required when DATABASE_URL is configured.')
        return psycopg2.connect(DATABASE_URL)
    return sqlite3.connect(DATABASE)


def _normalize_row(row):
    if row is None:
        return None
    if hasattr(row, 'keys'):
        return dict(row)
    return row


def _create_sqlite_init():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS users
            (id INTEGER PRIMARY KEY AUTOINCREMENT,
             username TEXT NOT NULL UNIQUE,
             email TEXT UNIQUE,
             password_hash TEXT NOT NULL,
             full_name TEXT,
             role TEXT DEFAULT 'user',
             is_active INTEGER DEFAULT 1,
             created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
             updated_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username ON users(username)')
    c.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(email)')

    c.execute('''CREATE TABLE IF NOT EXISTS reports
            (id INTEGER PRIMARY KEY AUTOINCREMENT,
             report_type TEXT NOT NULL,
             filename TEXT,
             timestamp TEXT,
             pothole_count INTEGER,
             unique_potholes INTEGER,
             runtime_seconds REAL,
             total_frames INTEGER,
             fps INTEGER,
             frames_with_detections INTEGER,
             report_path TEXT,
             latitude REAL,
             longitude REAL,
             created_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')

    c.execute('PRAGMA table_info(reports)')
    cols = [col[1] for col in c.fetchall()]
    if 'latitude' not in cols:
        c.execute('ALTER TABLE reports ADD COLUMN latitude REAL')
    if 'longitude' not in cols:
        c.execute('ALTER TABLE reports ADD COLUMN longitude REAL')

    c.execute('''CREATE TABLE IF NOT EXISTS report_files
            (id INTEGER PRIMARY KEY AUTOINCREMENT,
             report_id INTEGER,
             filename TEXT,
             mime_type TEXT,
             content BLOB,
             created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
             FOREIGN KEY(report_id) REFERENCES reports(id) ON DELETE CASCADE)''')

    conn.commit()
    conn.close()
    print('SQLite database initialized successfully')


def _create_postgres_init():
    conn = get_db_connection()
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id BIGSERIAL PRIMARY KEY,
        username VARCHAR(150) NOT NULL UNIQUE,
        email VARCHAR(255) UNIQUE,
        password_hash TEXT NOT NULL,
        full_name VARCHAR(255),
        role VARCHAR(50) DEFAULT 'user',
        is_active BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS reports (
        id BIGSERIAL PRIMARY KEY,
        report_type VARCHAR(50) NOT NULL,
        filename VARCHAR(255),
        timestamp VARCHAR(255),
        pothole_count INTEGER,
        unique_potholes INTEGER,
        runtime_seconds DOUBLE PRECISION,
        total_frames INTEGER,
        fps INTEGER,
        frames_with_detections INTEGER,
        report_path TEXT,
        latitude DOUBLE PRECISION,
        longitude DOUBLE PRECISION,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    c.execute("SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'reports' AND column_name = 'latitude')")
    if not c.fetchone()[0]:
        c.execute('ALTER TABLE reports ADD COLUMN latitude DOUBLE PRECISION')
    c.execute("SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'reports' AND column_name = 'longitude')")
    if not c.fetchone()[0]:
        c.execute('ALTER TABLE reports ADD COLUMN longitude DOUBLE PRECISION')

    c.execute('''CREATE TABLE IF NOT EXISTS report_files (
        id BIGSERIAL PRIMARY KEY,
        report_id BIGINT,
        filename VARCHAR(255),
        mime_type VARCHAR(100),
        content BYTEA,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (report_id) REFERENCES reports(id) ON DELETE CASCADE
    )''')

    conn.commit()
    conn.close()
    print('PostgreSQL database initialized successfully')


def init_database():
    """Initialize database with users/reports tables."""
    try:
        if is_postgres_db():
            _create_postgres_init()
        else:
            _create_sqlite_init()
    except Exception as e:
        print(f'Error initializing database: {e}')


def save_report_to_db(report_type, filename, report_data, report_path):
    """Save report information to the active database backend."""
    try:
        conn = get_db_connection()
        c = conn.cursor()

        loc = report_data.get('location', {}) if isinstance(report_data.get('location'), dict) else {}
        lat = loc.get('latitude', loc.get('lat', report_data.get('latitude', report_data.get('lat'))))
        lng = loc.get('longitude', loc.get('lng', report_data.get('longitude', report_data.get('lng'))))

        if (lat is None or lng is None) and report_data.get('pothole_locations'):
            try:
                first_p = list(report_data['pothole_locations'].values())[0]
                if isinstance(first_p, dict):
                    lat = first_p.get('lat', first_p.get('latitude'))
                    lng = first_p.get('lng', first_p.get('longitude'))
            except Exception:
                pass

        if report_type == 'image':
            if is_postgres_db():
                c.execute(
                    '''INSERT INTO reports (report_type, filename, timestamp, pothole_count, report_path, latitude, longitude)
                       VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id''',
                    (report_type, filename, report_data.get('timestamp'), report_data.get('pothole_count'), report_path, lat, lng)
                )
            else:
                c.execute(
                    '''INSERT INTO reports (report_type, filename, timestamp, pothole_count, report_path, latitude, longitude)
                       VALUES (?, ?, ?, ?, ?, ?, ?)''',
                    (report_type, filename, report_data.get('timestamp'), report_data.get('pothole_count'), report_path, lat, lng)
                )

        elif report_type == 'video':
            if is_postgres_db():
                c.execute(
                    '''INSERT INTO reports (report_type, filename, timestamp, total_frames, fps, frames_with_detections,
                       pothole_count, unique_potholes, report_path, latitude, longitude)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id''',
                    (report_type, filename, report_data.get('timestamp'), report_data.get('total_frames'), report_data.get('fps'),
                     report_data.get('frames_with_detections'), report_data.get('total_potholes_detected'),
                     report_data.get('unique_potholes'), report_path, lat, lng)
                )
            else:
                c.execute(
                    '''INSERT INTO reports (report_type, filename, timestamp, total_frames, fps, frames_with_detections,
                       pothole_count, unique_potholes, report_path, latitude, longitude)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (report_type, filename, report_data.get('timestamp'), report_data.get('total_frames'), report_data.get('fps'),
                     report_data.get('frames_with_detections'), report_data.get('total_potholes_detected'),
                     report_data.get('unique_potholes'), report_path, lat, lng)
                )

        elif report_type == 'camera':
            if is_postgres_db():
                c.execute(
                    '''INSERT INTO reports (report_type, timestamp, pothole_count, unique_potholes, runtime_seconds, report_path, latitude, longitude)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id''',
                    (report_type, report_data.get('timestamp'), report_data.get('total_detections'), report_data.get('unique_potholes'),
                     report_data.get('runtime_seconds'), report_path, lat, lng)
                )
            else:
                c.execute(
                    '''INSERT INTO reports (report_type, timestamp, pothole_count, unique_potholes, runtime_seconds, report_path, latitude, longitude)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                    (report_type, report_data.get('timestamp'), report_data.get('total_detections'), report_data.get('unique_potholes'),
                     report_data.get('runtime_seconds'), report_path, lat, lng)
                )

        conn.commit()
        report_id = c.fetchone()[0] if is_postgres_db() else c.lastrowid
        conn.close()
        print(f'{report_type.capitalize()} report saved to database (id={report_id})')
        return report_id
    except Exception as e:
        print(f'Error saving report to database: {e}')
        return None


def get_reports_from_db():
    """Fetch all reports from the active database backend."""
    try:
        conn = get_db_connection()
        c = conn.cursor()

        c.execute('''SELECT id, report_type, filename, timestamp, pothole_count, unique_potholes,
                          runtime_seconds, report_path, created_at, latitude, longitude
                     FROM reports ORDER BY created_at DESC''')
        rows = c.fetchall()
        conn.close()

        reports = {'image_reports': [], 'video_reports': [], 'camera_reports': []}
        for row in rows:
            if is_postgres_db():
                report_id, report_type, filename, timestamp, pothole_count, unique_potholes, runtime_seconds, report_path, created_at, lat, lng = row
            else:
                report_id, report_type, filename, timestamp, pothole_count, unique_potholes, runtime_seconds, report_path, created_at, lat, lng = row

            created_at_value = created_at
            if isinstance(created_at_value, datetime):
                created = created_at_value.timestamp()
            elif isinstance(created_at_value, str):
                try:
                    created = datetime.strptime(created_at_value, '%Y-%m-%d %H:%M:%S').timestamp()
                except ValueError:
                    created = 0
            else:
                created = 0

            report_item = {
                'id': report_id,
                'name': filename or f'Report_{report_id}',
                'path': report_path,
                'timestamp': timestamp,
                'created_at': created_at,
                'created': created,
                'latitude': lat,
                'longitude': lng
            }

            if report_type == 'image':
                report_item['pothole_count'] = pothole_count
                reports['image_reports'].append(report_item)
            elif report_type == 'video':
                report_item['pothole_count'] = pothole_count
                report_item['unique_potholes'] = unique_potholes
                reports['video_reports'].append(report_item)
            elif report_type == 'camera':
                report_item['pothole_count'] = pothole_count
                report_item['unique_potholes'] = unique_potholes
                report_item['runtime'] = runtime_seconds
                reports['camera_reports'].append(report_item)

        return reports
    except Exception as e:
        print(f'Error fetching reports from database: {e}')
        return {'image_reports': [], 'video_reports': [], 'camera_reports': []}


def get_database_stats():
    """Return report totals grouped by type."""
    try:
        conn = get_db_connection()
        c = conn.cursor()

        c.execute('SELECT COUNT(*) FROM reports')
        total_reports = c.fetchone()[0]

        c.execute('SELECT report_type, COUNT(*) FROM reports GROUP BY report_type')
        by_type = c.fetchall()

        conn.close()
        stats = {
            'total_reports': total_reports,
            'by_type': {row[0]: row[1] for row in by_type},
            'database_path': DATABASE,
            'database_engine': DB_ENGINE,
        }
        return stats
    except Exception as e:
        print(f'Error fetching database stats: {e}')
        return {'total_reports': 0, 'by_type': {}, 'database_path': DATABASE, 'database_engine': DB_ENGINE, 'error': str(e)}


def save_report_file(report_id, filename, content_bytes, mime_type='text/plain'):
    """Save a report file/blob associated with a report record."""
    try:
        conn = get_db_connection()
        c = conn.cursor()
        if is_postgres_db():
            c.execute('''INSERT INTO report_files (report_id, filename, mime_type, content)
                         VALUES (%s, %s, %s, %s) RETURNING id''', (report_id, filename, mime_type, content_bytes))
            file_id = c.fetchone()[0]
        else:
            c.execute('''INSERT INTO report_files (report_id, filename, mime_type, content)
                         VALUES (?, ?, ?, ?)''', (report_id, filename, mime_type, content_bytes))
            file_id = c.lastrowid
        conn.commit()
        conn.close()
        print(f'Report file saved to DB (file_id={file_id}, report_id={report_id})')
        return file_id
    except Exception as e:
        print(f'Error saving report file to DB: {e}')
        return None


def get_report_file(report_id):
    """Retrieve the latest report file blob for a given report_id."""
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('''SELECT id, filename, mime_type, content FROM report_files
                     WHERE report_id = %s ORDER BY created_at DESC LIMIT 1'''
                  if is_postgres_db() else
                  '''SELECT id, filename, mime_type, content FROM report_files
                     WHERE report_id = ? ORDER BY created_at DESC LIMIT 1''',
                  (report_id,) if is_postgres_db() else (report_id,))
        row = c.fetchone()
        conn.close()
        if not row:
            return None
        if is_postgres_db():
            file_id, filename, mime_type, content = row['id'], row['filename'], row['mime_type'], row['content']
        else:
            file_id, filename, mime_type, content = row
        return {'file_id': file_id, 'filename': filename, 'mime_type': mime_type, 'content': content}
    except Exception as e:
        print(f'Error fetching report file from DB: {e}')
        return None


def delete_report_from_db(report_id):
    """Delete a report from the active database backend."""
    try:
        conn = get_db_connection()
        c = conn.cursor()
        if is_postgres_db():
            c.execute('DELETE FROM reports WHERE id = %s', (report_id,))
        else:
            c.execute('DELETE FROM reports WHERE id = ?', (report_id,))
        conn.commit()
        conn.close()
        print(f'Report {report_id} deleted from database')
        return True
    except Exception as e:
        print(f'Error deleting report from database: {e}')
        return False


def get_report_by_id(report_id):
    """Fetch a specific report from the active database backend."""
    try:
        conn = get_db_connection()
        c = conn.cursor()
        if is_postgres_db():
            c.execute('''SELECT id, report_type, filename, timestamp, pothole_count,
                               unique_potholes, runtime_seconds, report_path, created_at, latitude, longitude
                        FROM reports WHERE id = %s''', (report_id,))
        else:
            c.execute('''SELECT id, report_type, filename, timestamp, pothole_count,
                               unique_potholes, runtime_seconds, report_path, created_at, latitude, longitude
                        FROM reports WHERE id = ?''', (report_id,))
        row = c.fetchone()
        conn.close()
        if not row:
            return None

        if is_postgres_db():
            report_id, report_type, filename, timestamp, pothole_count, unique_potholes, runtime_seconds, report_path, created_at, lat, lng = row
        else:
            report_id, report_type, filename, timestamp, pothole_count, unique_potholes, runtime_seconds, report_path, created_at, lat, lng = row

        report_item = {
            'id': report_id,
            'report_type': report_type,
            'name': filename or f'Report_{report_id}',
            'path': report_path,
            'timestamp': timestamp,
            'created_at': created_at,
            'pothole_count': pothole_count,
            'unique_potholes': unique_potholes,
            'runtime': runtime_seconds,
            'latitude': lat,
            'longitude': lng
        }
        return report_item
    except Exception as e:
        print(f'Error fetching report from database: {e}')
        return None


def update_report_location_in_db(report_id, latitude, longitude):
    """Update latitude and longitude for a given report ID in the active database backend."""
    try:
        conn = get_db_connection()
        c = conn.cursor()
        if is_postgres_db():
            c.execute('UPDATE reports SET latitude = %s, longitude = %s WHERE id = %s', (latitude, longitude, report_id))
        else:
            c.execute('UPDATE reports SET latitude = ?, longitude = ? WHERE id = ?', (latitude, longitude, report_id))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f'Error updating report location in db: {e}')
        return False

