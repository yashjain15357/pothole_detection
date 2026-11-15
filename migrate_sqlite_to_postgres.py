import os
import sqlite3
from pathlib import Path

try:
    import psycopg2
except ImportError:
    raise SystemExit('Install psycopg2-binary first: pip install psycopg2-binary')


SQLITE_DB = Path('pothole_reports.db')
POSTGRES_URL = os.getenv('DATABASE_URL')

if not POSTGRES_URL:
    raise SystemExit('DATABASE_URL is not set. Add it to your environment first.')


def migrate_users(conn_pg, cur_pg, cur_sqlite):
    rows = cur_sqlite.execute('SELECT id, username, email, password_hash, full_name, role, is_active, created_at, updated_at FROM users').fetchall()
    for row in rows:
        cur_pg.execute(
            '''
            INSERT INTO users (id, username, email, password_hash, full_name, role, is_active, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO NOTHING
            ''',
            row
        )
    conn_pg.commit()


def migrate_reports(conn_pg, cur_pg, cur_sqlite):
    rows = cur_sqlite.execute('''
        SELECT id, report_type, filename, timestamp, pothole_count, unique_potholes,
               runtime_seconds, total_frames, fps, frames_with_detections, report_path,
               latitude, longitude, created_at
        FROM reports
    ''').fetchall()

    for row in rows:
        cur_pg.execute(
            '''
            INSERT INTO reports (
                id, report_type, filename, timestamp, pothole_count, unique_potholes,
                runtime_seconds, total_frames, fps, frames_with_detections, report_path,
                latitude, longitude, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO NOTHING
            ''',
            row
        )
    conn_pg.commit()


def migrate_report_files(conn_pg, cur_pg, cur_sqlite):
    rows = cur_sqlite.execute('SELECT id, report_id, filename, mime_type, content, created_at FROM report_files').fetchall()
    for row in rows:
        cur_pg.execute(
            '''
            INSERT INTO report_files (id, report_id, filename, mime_type, content, created_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO NOTHING
            ''',
            row
        )
    conn_pg.commit()


def main():
    sqlite_conn = sqlite3.connect(SQLITE_DB)
    sqlite_cur = sqlite_conn.cursor()

    pg_conn = psycopg2.connect(POSTGRES_URL)
    pg_cur = pg_conn.cursor()

    pg_cur.execute('SELECT 1 FROM information_schema.tables WHERE table_name = %s', ('users',))
    if not pg_cur.fetchone():
        pg_cur.execute('''
            CREATE TABLE users (
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

    pg_cur.execute('SELECT 1 FROM information_schema.tables WHERE table_name = %s', ('reports',))
    if not pg_cur.fetchone():
        pg_cur.execute('''
            CREATE TABLE reports (
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
            )
        ''')

    pg_cur.execute('SELECT 1 FROM information_schema.tables WHERE table_name = %s', ('report_files',))
    if not pg_cur.fetchone():
        pg_cur.execute('''
            CREATE TABLE report_files (
                id BIGSERIAL PRIMARY KEY,
                report_id BIGINT,
                filename VARCHAR(255),
                mime_type VARCHAR(100),
                content BYTEA,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (report_id) REFERENCES reports(id) ON DELETE CASCADE
            )
        ''')

    migrate_users(pg_conn, pg_cur, sqlite_cur)
    migrate_reports(pg_conn, pg_cur, sqlite_cur)
    migrate_report_files(pg_conn, pg_cur, sqlite_cur)

    sqlite_conn.close()
    pg_conn.close()
    print('SQLite data migrated to PostgreSQL successfully.')


if __name__ == '__main__':
    main()
