"""
Database Module for Pothole Detection System
Handles all database operations for storing and retrieving reports
"""

import sqlite3
from datetime import datetime
from pathlib import Path

# Database configuration
DATABASE = 'pothole_reports.db'


def init_database():
    """Initialize database with reports table"""
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        
        # Create reports table
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
                 created_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')

        # Table to store report files/blobs (text or generated PDFs)
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
        print("✓ Database initialized successfully")
    except Exception as e:
        print(f"Error initializing database: {e}")


def save_report_to_db(report_type, filename, report_data, report_path):
    """
    Save report information to database
    
    Args:
        report_type: Type of report ('image', 'video', or 'camera')
        filename: Original filename
        report_data: Report data dictionary
        report_path: Path to the report file
    """
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        
        if report_type == 'image':
            c.execute('''INSERT INTO reports 
                        (report_type, filename, timestamp, pothole_count, report_path)
                        VALUES (?, ?, ?, ?, ?)''',
                     (report_type, filename, report_data.get('timestamp'), 
                      report_data.get('pothole_count'), report_path))
        
        elif report_type == 'video':
            c.execute('''INSERT INTO reports 
                        (report_type, filename, timestamp, total_frames, fps, 
                         frames_with_detections, pothole_count, unique_potholes, report_path)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                     (report_type, filename, report_data.get('timestamp'),
                      report_data.get('total_frames'), report_data.get('fps'),
                      report_data.get('frames_with_detections'),
                      report_data.get('total_potholes_detected'),
                      report_data.get('unique_potholes'), report_path))
        
        elif report_type == 'camera':
            c.execute('''INSERT INTO reports 
                        (report_type, timestamp, pothole_count, unique_potholes, 
                         runtime_seconds, report_path)
                        VALUES (?, ?, ?, ?, ?, ?)''',
                     (report_type, report_data.get('timestamp'),
                      report_data.get('total_detections'),
                      report_data.get('unique_potholes'),
                      report_data.get('runtime_seconds'), report_path))
        
        conn.commit()
        report_id = c.lastrowid
        conn.close()
        print(f"✓ {report_type.capitalize()} report saved to database (id={report_id})")
        return report_id
    except Exception as e:
        print(f"Error saving report to database: {e}")
        return None


def get_reports_from_db():
    """
    Fetch all reports from database
    
    Returns:
        Dictionary with reports organized by type (image, video, camera)
    """
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        
        c.execute('''SELECT id, report_type, filename, timestamp, pothole_count, 
                           unique_potholes, runtime_seconds, report_path, created_at
                    FROM reports ORDER BY created_at DESC''')
        
        rows = c.fetchall()
        conn.close()
        
        reports = {
            'image_reports': [],
            'video_reports': [],
            'camera_reports': []
        }
        
        for row in rows:
            report_id, report_type, filename, timestamp, pothole_count, unique_potholes, runtime_seconds, report_path, created_at = row
            
            report_item = {
                'id': report_id,
                'name': filename or f"Report_{report_id}",
                'path': report_path,
                'timestamp': timestamp,
                'created_at': created_at,
                'created': datetime.strptime(created_at, '%Y-%m-%d %H:%M:%S').timestamp() if created_at else 0
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
        print(f"Error fetching reports from database: {e}")
        return {
            'image_reports': [],
            'video_reports': [],
            'camera_reports': []
        }


def get_database_stats():
    """
    Get database statistics
    
    Returns:
        Dictionary with total count and count by report type
    """
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        
        c.execute('SELECT COUNT(*) FROM reports')
        total_reports = c.fetchone()[0]
        
        c.execute('SELECT report_type, COUNT(*) FROM reports GROUP BY report_type')
        by_type = c.fetchall()
        
        conn.close()
        
        stats = {
            'total_reports': total_reports,
            'by_type': {report_type: count for report_type, count in by_type},
            'database_path': DATABASE
        }
        
        return stats
    except Exception as e:
        print(f"Error fetching database stats: {e}")
        return {
            'total_reports': 0,
            'by_type': {},
            'database_path': DATABASE,
            'error': str(e)
        }


def save_report_file(report_id, filename, content_bytes, mime_type='text/plain'):
    """Save a report file/blob associated with a report record."""
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('''INSERT INTO report_files (report_id, filename, mime_type, content)
                     VALUES (?, ?, ?, ?)''', (report_id, filename, mime_type, content_bytes))
        conn.commit()
        file_id = c.lastrowid
        conn.close()
        print(f"✓ Report file saved to DB (file_id={file_id}, report_id={report_id})")
        return file_id
    except Exception as e:
        print(f"Error saving report file to DB: {e}")
        return None


def get_report_file(report_id):
    """Retrieve the latest report file blob for a given report_id."""
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('''SELECT id, filename, mime_type, content FROM report_files
                     WHERE report_id = ? ORDER BY created_at DESC LIMIT 1''', (report_id,))
        row = c.fetchone()
        conn.close()
        if not row:
            return None
        file_id, filename, mime_type, content = row
        return {
            'file_id': file_id,
            'filename': filename,
            'mime_type': mime_type,
            'content': content
        }
    except Exception as e:
        print(f"Error fetching report file from DB: {e}")
        return None


def delete_report_from_db(report_id):
    """
    Delete a report from database
    
    Args:
        report_id: ID of the report to delete
        
    Returns:
        Boolean indicating success
    """
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        
        c.execute('DELETE FROM reports WHERE id = ?', (report_id,))
        conn.commit()
        conn.close()
        
        print(f"✓ Report {report_id} deleted from database")
        return True
    except Exception as e:
        print(f"Error deleting report from database: {e}")
        return False


def get_report_by_id(report_id):
    """
    Fetch a specific report from database
    
    Args:
        report_id: ID of the report to fetch
        
    Returns:
        Dictionary with report data or None if not found
    """
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        
        c.execute('''SELECT id, report_type, filename, timestamp, pothole_count, 
                           unique_potholes, runtime_seconds, report_path, created_at
                    FROM reports WHERE id = ?''', (report_id,))
        
        row = c.fetchone()
        conn.close()
        
        if not row:
            return None
        
        report_id, report_type, filename, timestamp, pothole_count, unique_potholes, runtime_seconds, report_path, created_at = row
        
        report_item = {
            'id': report_id,
            'report_type': report_type,
            'name': filename or f"Report_{report_id}",
            'path': report_path,
            'timestamp': timestamp,
            'created_at': created_at,
            'pothole_count': pothole_count,
            'unique_potholes': unique_potholes,
            'runtime': runtime_seconds
        }
        
        return report_item
    except Exception as e:
        print(f"Error fetching report from database: {e}")
        return None
