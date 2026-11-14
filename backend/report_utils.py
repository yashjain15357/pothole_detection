import json
import re
from pathlib import Path


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


def extract_location_from_text(report_text: str):
    """Extract latitude/longitude from plain-text report content if present."""
    if not report_text:
        return None

    lat_match = re.search(r'Latitude\s*:\s*([-+]?\d+(?:\.\d+)?)', report_text, re.IGNORECASE)
    lng_match = re.search(r'Longitude\s*:\s*([-+]?\d+(?:\.\d+)?)', report_text, re.IGNORECASE)

    if lat_match and lng_match:
        try:
            return {
                'latitude': float(lat_match.group(1)),
                'longitude': float(lng_match.group(1)),
            }
        except (TypeError, ValueError):
            return None

    return None


def get_location_for_report(report, report_text=None):
    """Get location for a report from text, paired JSON, or location history files."""
    location = extract_location_from_text(report_text or '')
    if location:
        return location

    report_path = (report or {}).get('path', '')
    resolved_path = resolve_report_file(report_path)
    if resolved_path:
        candidate_json = resolved_path.with_suffix('.json')
        if candidate_json.exists():
            try:
                with open(candidate_json, 'r', encoding='utf-8') as jf:
                    payload = json.load(jf)
                loc = payload.get('location', {}) if isinstance(payload, dict) else {}
                if isinstance(loc, dict) and 'latitude' in loc and 'longitude' in loc:
                    return {
                        'latitude': float(loc.get('latitude')),
                        'longitude': float(loc.get('longitude')),
                    }
            except Exception:
                pass

    report_type = (report or {}).get('report_type', '')
    report_name = str((report or {}).get('name', '')).strip()

    location_dirs = []
    if report_type == 'image':
        location_dirs = [Path('IN_image/locations'), Path('/tmp/IN_image/locations')]
    elif report_type == 'video':
        location_dirs = [Path('IN_vedio/locations'), Path('/tmp/IN_vedio/locations')]

    for location_dir in location_dirs:
        if not location_dir.exists():
            continue

        try:
            json_files = sorted(location_dir.glob('*.json'), reverse=True)
            for file_path in json_files:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        payload = json.load(f)

                    if not isinstance(payload, dict):
                        continue

                    payload_name = str(payload.get('filename', '')).strip()
                    if report_name and payload_name and payload_name != report_name:
                        continue

                    if 'latitude' in payload and 'longitude' in payload:
                        return {
                            'latitude': float(payload.get('latitude')),
                            'longitude': float(payload.get('longitude')),
                        }
                except Exception:
                    continue

            if json_files:
                try:
                    with open(json_files[0], 'r', encoding='utf-8') as f:
                        payload = json.load(f)
                    if isinstance(payload, dict) and 'latitude' in payload and 'longitude' in payload:
                        return {
                            'latitude': float(payload.get('latitude')),
                            'longitude': float(payload.get('longitude')),
                        }
                except Exception:
                    pass
        except Exception:
            continue

    return None
