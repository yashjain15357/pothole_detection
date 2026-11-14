from flask import Blueprint, jsonify, request
from pathlib import Path
from datetime import datetime
import os
import smtplib
import ssl

from database import get_report_by_id, get_report_file
from report_utils import resolve_report_file
from config import SMTP_SERVER, SMTP_PORT, SMTP_EMAIL, SMTP_APP_PASSWORD, SMTP_USE_STARTTLS

bp = Blueprint('email', __name__)


@bp.route('/api/smtp-config', methods=['GET', 'POST'])
def smtp_config_api():
    from app import app, SMTP_SERVER as app_smtp_server, SMTP_PORT as app_smtp_port, SMTP_EMAIL as app_smtp_email, SMTP_APP_PASSWORD as app_smtp_password, SMTP_USE_STARTTLS as app_starttls
    from app import app
    config_file = Path('smtp_config.json')

    if request.method == 'GET':
        return jsonify({
            'success': True,
            'smtp_email': app_smtp_email,
            'configured': bool(app_smtp_email and app_smtp_password),
            'smtp_server': app_smtp_server,
            'smtp_port': app_smtp_port,
        }), 200

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
        'SMTP_USE_STARTTLS': True,
    }

    try:
        with open(config_file, 'w', encoding='utf-8') as f:
            import json
            json.dump(config, f, indent=2)

        import app as app_module
        app_module.SMTP_SERVER = server
        app_module.SMTP_PORT = port
        app_module.SMTP_EMAIL = email
        app_module.SMTP_APP_PASSWORD = password
        app_module.SMTP_USE_STARTTLS = True

        return jsonify({'success': True, 'message': 'SMTP configuration saved successfully!'}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/send-report-email', methods=['POST'])
def send_report_email():
    try:
        data = request.get_json() or {}
        report_id = data.get('report_id')
        report_path_raw = data.get('report_path', '')
        report_name = data.get('report_name', 'report')
        recipient_email = data.get('recipient_email', '').strip()
        message = data.get('message', '')

        if not recipient_email:
            return jsonify({'success': False, 'error': 'Recipient email is required'}), 400

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
                        lat_val = f"{float(r_item['latitude']):.6f}" if r_item.get('latitude') else 'Not Geotagged'
                        lng_val = f"{float(r_item['longitude']):.6f}" if r_item.get('longitude') else 'Not Geotagged'
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

        if not SMTP_EMAIL or not SMTP_APP_PASSWORD:
            return jsonify({'success': False, 'error': 'SMTP is not configured.'}), 400

        if '@' in SMTP_SERVER or '.' not in SMTP_SERVER:
            return jsonify({'success': False, 'error': f'Invalid SMTP server configured: {SMTP_SERVER}. Use smtp.gmail.com for Gmail.'}), 400

        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        from email.mime.base import MIMEBase
        from email import encoders

        msg = MIMEMultipart()
        msg['to'] = recipient_email
        msg['subject'] = f'Pothole Detection Report - {report_name}'

        body = f"""
        <html>
            <body>
                <h2>🛣️ FIX MY CITY - Pothole Detection Report</h2>
                <p>Dear Authority / User,</p>
                <p>Please find attached the report: <strong>{report_name}</strong></p>
                {f'<p>{message}</p>' if message else ''}
            </body>
        </html>
        """
        msg.attach(MIMEText(body, 'html'))

        try:
            with open(file_path, 'rb') as attachment:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(attachment.read())
                encoders.encode_base64(part)
                part.add_header('Content-Disposition', f'attachment; filename= {file_path.name}')
                msg.attach(part)
        except Exception as e:
            return jsonify({'success': False, 'error': f'Failed to attach file: {str(e)}'}), 500

        try:
            context = ssl.create_default_context()
            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=30) as server:
                if SMTP_USE_STARTTLS:
                    server.ehlo()
                    server.starttls(context=context)
                    server.ehlo()
                server.login(SMTP_EMAIL, SMTP_APP_PASSWORD)
                server.sendmail(SMTP_EMAIL, recipient_email, msg.as_string())

            return jsonify({'success': True, 'message': f'Report sent successfully to {recipient_email}'}), 200
        except smtplib.SMTPAuthenticationError:
            return jsonify({'success': False, 'error': 'Gmail authentication failed. Please check your Google App Password.'}), 400
        except Exception as error:
            return jsonify({'success': False, 'error': f'Failed to send email via SMTP: {str(error)}'}), 500
        finally:
            if temp_file_to_clean and temp_file_to_clean.exists():
                try:
                    os.unlink(str(temp_file_to_clean))
                except Exception:
                    pass
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
