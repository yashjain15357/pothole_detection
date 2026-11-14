from flask import Blueprint, jsonify, request, current_app
from datetime import datetime
import base64
import gc
import numpy as np
import cv2

from auth_utils import login_required
from process import process_image, process_video, update_report_with_location, get_model

bp = Blueprint('detection', __name__)


def get_camera_session():
    session = current_app.config.setdefault('camera_session', {
        'active': False,
        'previous_centroids': {},
        'next_pothole_id': 1,
        'unique_pothole_ids': set(),
        'distance_threshold': 50,
    })
    return session


@bp.route('/upload-image', methods=['POST'])
@login_required
def upload_image():
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No file provided'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'No file selected'}), 400

    from config import SUPPORTED_IMAGES
    if not file.filename.lower().endswith(SUPPORTED_IMAGES):
        return jsonify({'success': False, 'error': 'Invalid file type. Please upload an image.'}), 400

    try:
        from pathlib import Path
        temp_dir = Path('/tmp/pothole_uploads')
        temp_dir.mkdir(exist_ok=True, parents=True)
        filepath = temp_dir / file.filename
        file.save(str(filepath))

        result, error = process_image(str(filepath))
        if error:
            return jsonify({'success': False, 'error': error}), 500

        latitude = request.form.get('latitude')
        longitude = request.form.get('longitude')
        if latitude and longitude:
            try:
                result['report']['location'] = {'latitude': float(latitude), 'longitude': float(longitude)}
                update_report_with_location(result['report'], float(latitude), float(longitude))
            except (TypeError, ValueError):
                pass

        return jsonify(result), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/upload-video', methods=['POST'])
@login_required
def upload_video():
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No file provided'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'No file selected'}), 400

    from config import SUPPORTED_VIDEOS
    if not file.filename.lower().endswith(SUPPORTED_VIDEOS):
        return jsonify({'success': False, 'error': 'Invalid file type. Please upload a video.'}), 400

    try:
        from pathlib import Path
        temp_dir = Path('/tmp/pothole_uploads')
        temp_dir.mkdir(exist_ok=True, parents=True)
        filepath = temp_dir / file.filename
        file.save(str(filepath))

        result, error = process_video(str(filepath))
        if error:
            return jsonify({'success': False, 'error': error}), 500

        return jsonify(result), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/start-camera-session', methods=['POST'])
@login_required
def start_camera_session():
    session = get_camera_session()
    session.update({
        'active': True,
        'previous_centroids': {},
        'next_pothole_id': 1,
        'unique_pothole_ids': set(),
        'distance_threshold': 50,
    })
    return jsonify({'success': True, 'message': 'Camera session initialized'}), 200


@bp.route('/health')
def health():
    yolo_model = get_model()
    return jsonify({
        'status': 'healthy',
        'model_loaded': yolo_model is not None,
        'timestamp': datetime.now().isoformat(),
    }), 200


@bp.route('/detect-frame', methods=['POST'])
@login_required
def detect_frame():
    yolo_model = get_model()
    if yolo_model is None:
        return jsonify({'success': False, 'error': 'Model not loaded'}), 500

    camera_session = get_camera_session()

    try:
        data = request.json or {}
        if 'image' not in data:
            return jsonify({'success': False, 'error': 'No image data'}), 400

        image_str = data['image']
        if image_str.startswith('data:'):
            if ',' in image_str:
                image_str = image_str.split(',', 1)[1]
            else:
                return jsonify({'success': False, 'error': 'Invalid data URI format'}), 400

        if not image_str or len(image_str) < 50:
            return jsonify({'success': False, 'error': 'Image data is too small'}), 400

        try:
            img_bytes = base64.b64decode(image_str)
        except Exception as b64_error:
            return jsonify({'success': False, 'error': f'Invalid base64 format: {b64_error}'}), 400

        if not img_bytes:
            return jsonify({'success': False, 'error': 'Decoded image is empty'}), 400

        nparr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return jsonify({'success': False, 'error': 'Failed to decode JPEG data'}), 400

        orig_h, orig_w = img.shape[:2]
        results = yolo_model.predict(source=img, conf=0.25, imgsz=416, verbose=False, device='cpu')
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

                pothole_id = None
                for prev_id, prev_centroid in camera_session.get('previous_centroids', {}).items():
                    distance = np.sqrt((cx - prev_centroid[0]) ** 2 + (cy - prev_centroid[1]) ** 2)
                    if distance < camera_session.get('distance_threshold', 50):
                        pothole_id = prev_id
                        break

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
                    'confidence': f'{conf:.2%}',
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
            'boxes': boxes,
        }), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
