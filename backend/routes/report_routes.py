from flask import Blueprint, jsonify, request, send_file
from pathlib import Path

from report_utils import get_location_for_report, resolve_report_file
from database import get_report_by_id, get_report_file

bp = Blueprint('reports', __name__)


@bp.route('/reports')
def reports():
    from database import get_reports_from_db
    return jsonify(get_reports_from_db()), 200


@bp.route('/reports-stats')
def reports_stats():
    from database import get_database_stats
    return jsonify(get_database_stats()), 200


@bp.route('/report/<path:report_path>')
def get_report(report_path):
    try:
        report_path = report_path.replace('/', '\\')
        file_path = Path(report_path)

        if not file_path.exists():
            return jsonify({'error': f'Report not found: {file_path}'}), 404

        with open(file_path, 'r', encoding='utf-8') as f:
            return jsonify({'content': f.read()}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/report-by-id/<int:report_id>')
def get_report_by_id_route(report_id):
    try:
        report = get_report_by_id(report_id)
        if not report:
            return jsonify({'success': False, 'error': f'Report #{report_id} not found in database'}), 404

        report_text = None

        try:
            file_entry = get_report_file(report_id)
            if file_entry and file_entry.get('content'):
                c = file_entry['content']
                report_text = c.decode('utf-8', errors='replace') if isinstance(c, bytes) else str(c)
        except Exception:
            pass

        if not report_text and report.get('path'):
            file_path = resolve_report_file(report['path'])
            if file_path and file_path.exists():
                with open(file_path, 'r', encoding='utf-8') as f:
                    report_text = f.read()

        if not report_text:
            lat_str = f"{float(report['latitude']):.6f}" if report.get('latitude') else 'Not Geotagged'
            lng_str = f"{float(report['longitude']):.6f}" if report.get('longitude') else 'Not Geotagged'
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
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/download-report/<path:report_path>')
def download_report(report_path):
    file_path = resolve_report_file(report_path)
    if not file_path:
        return jsonify({'error': 'Report not found'}), 404

    download_name = file_path.name
    mimetype = 'text/plain' if file_path.suffix.lower() == '.txt' else 'application/octet-stream'

    try:
        return send_file(str(file_path), as_attachment=True, download_name=download_name, mimetype=mimetype)
    except TypeError:
        return send_file(str(file_path), as_attachment=True, attachment_filename=download_name, mimetype=mimetype)


@bp.route('/download-report-pdf/<int:report_id>')
def download_report_pdf(report_id):
    from io import BytesIO
    import re
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter

    report = get_report_by_id(report_id)
    if not report:
        return jsonify({'error': 'Report not found'}), 404

    file_entry = get_report_file(report_id)
    report_text = None
    if file_entry and file_entry.get('content'):
        content = file_entry['content']
        report_text = content.decode('utf-8', errors='replace') if isinstance(content, bytes) else str(content)

    if not report_text and report.get('path'):
        p = resolve_report_file(report.get('path'))
        if p and p.exists():
            with open(p, 'r', encoding='utf-8') as f:
                report_text = f.read()

    if not report_text:
        return jsonify({'error': 'No report content available to generate PDF'}), 404

    location = get_location_for_report(report, report_text)
    if location and not re.search(r'Latitude\s*:', report_text, re.IGNORECASE):
        report_text = (
            'LOCATION\n'
            f"Latitude: {location['latitude']:.6f}\n"
            f"Longitude: {location['longitude']:.6f}\n"
            + ('-' * 60) + '\n\n'
            + report_text
        )

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    margin = 40
    y = height - margin
    line_height = 12
    title = report.get('name') or f'Report_{report_id}'
    c.setFont('Helvetica-Bold', 14)
    c.drawString(margin, y, title)
    y -= (line_height * 2)

    c.setFont('Helvetica', 10)
    for raw_line in report_text.splitlines():
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
    return send_file(buffer, as_attachment=True, download_name=download_name, mimetype='application/pdf')
