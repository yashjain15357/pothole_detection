# Flask Application for Pothole Detection System
import os
# Set YOLO config directory before importing YOLO
os.environ['YOLO_CONFIG_DIR'] = '/tmp/Ultralytics'

from flask import Flask, render_template, request, jsonify, send_file
from pathlib import Path
import cv2
import numpy as np
from datetime import datetime
from ultralytics import YOLO
import json
import base64
from io import BytesIO

import re

# Import database functions
from database import init_database, save_report_to_db, get_reports_from_db, get_database_stats, get_report_by_id

app = Flask(__name__)

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

# Load YOLO model
try:
    model_path = Path("best.pt")
    if not model_path.exists():
        print(f"⚠️ Model not found at {model_path.resolve()}")
        model = None
    else:
        model = YOLO(str(model_path))
        print(f"✓ Model loaded from {model_path}")
except Exception as e:
    print(f"Error loading model: {e}")
    model = None


def process_image(image_path):
    """Process image and detect potholes"""
    if model is None:
        return None, "Model not loaded"
    
    try:
        file_name = Path(image_path).name
        
        # Prediction
        results = model.predict(source=image_path, conf=0.2, imgsz=640)
        result = results[0]
        pothole_count = len(result.boxes) if result.boxes is not None else 0

        # Build report
        report_data = {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'filename': file_name,
            'pothole_count': pothole_count,
            'detections': []
        }

        # Get detection details
        if pothole_count > 0:
            for i, box in enumerate(result.boxes, 1):
                conf = box.conf.item()
                x1, y1, x2, y2 = box.xyxy[0]
                width = x2 - x1
                height = y2 - y1
                report_data['detections'].append({
                    'pothole_id': i,
                    'confidence': f"{conf:.2%}",
                    'width_px': f"{width:.0f}",
                    'height_px': f"{height:.0f}",
                    'x1': int(x1),
                    'y1': int(y1),
                    'x2': int(x2),
                    'y2': int(y2)
                })

        # Save report - use /tmp for Render compatibility
        report_dir = Path("/tmp/IN_image")
        report_dir.mkdir(exist_ok=True, parents=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Save as JSON
        report_file_json = report_dir / f"pothole_report_{timestamp}.json"
        with open(report_file_json, 'w', encoding='utf-8') as rf:
            json.dump(report_data, rf, indent=2)
        
        # Save as TXT
        report_file_txt = report_dir / f"pothole_report_{timestamp}.txt"
        with open(report_file_txt, 'w', encoding='utf-8') as rf:
            rf.write("=" * 60 + "\n")
            rf.write("POTHOLE DETECTION REPORT\n")
            rf.write("=" * 60 + "\n")
            rf.write(f"Timestamp: {report_data['timestamp']}\n")
            rf.write(f"Image: {file_name}\n")
            rf.write(f"Potholes Detected: {pothole_count}\n")
            rf.write("=" * 60 + "\n")
            
            if pothole_count > 0:
                rf.write("\nDetection Details:\n")
                rf.write("-" * 60 + "\n")
                for det in report_data['detections']:
                    rf.write(f"Pothole {det['pothole_id']}: Confidence = {det['confidence']}, Width = {det['width_px']}px, Height = {det['height_px']}px\n")
            else:
                rf.write("\nNo potholes detected\n")

        # Create annotated image
        img = cv2.imread(image_path)
        
        if img is None:
            return None, f"Failed to load image: {image_path}"
        
        # Draw bounding boxes on detected potholes
        if result.boxes is not None and len(result.boxes) > 0:
            for box in result.boxes:
                x1, y1, x2, y2 = box.xyxy[0]
                x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
                conf = box.conf.item()
                
                # Draw rectangle with bright cyan color (easier to see)
                cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 255), 3)
                
                # Draw filled background for text
                label = f"Pothole: {conf:.2%}"
                text_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
                cv2.rectangle(img, (x1, y1 - text_size[1] - 8), (x1 + text_size[0] + 4, y1), (0, 255, 255), -1)
                
                # Put text
                cv2.putText(img, label, (x1 + 2, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)

        # Save annotated image to /tmp
        output_path = report_dir / f"annotated_{timestamp}.jpg"
        cv2.imwrite(str(output_path), img)

        # Convert to base64 for display
        _, buffer = cv2.imencode('.jpg', img)
        img_base64 = base64.b64encode(buffer).decode('utf-8')

        # Save report to database
        save_report_to_db('image', file_name, report_data, str(report_file_txt))

        return {
            'success': True,
            'report': report_data,
            'image_base64': img_base64,
            'report_file': str(report_file_txt)
        }, None

    except Exception as e:
        return None, str(e)


def update_report_with_location(report_data, latitude, longitude):
    """Update the most recent report file with location data"""
    try:
        report_dir = Path("IN_image")
        report_files = sorted(report_dir.glob("pothole_report_*.json"), reverse=True)
        
        if report_files:
            latest_report_file = report_files[0]
            
            # Read existing report
            with open(latest_report_file, 'r', encoding='utf-8') as f:
                existing_report = json.load(f)
            
            # Add location to the report
            existing_report['location'] = {
                'latitude': latitude,
                'longitude': longitude
            }
            
            # Save updated report
            with open(latest_report_file, 'w', encoding='utf-8') as f:
                json.dump(existing_report, f, indent=2)
            
            # Also update the TXT file
            txt_files = sorted(report_dir.glob("pothole_report_*.txt"), reverse=True)
            if txt_files:
                txt_file = txt_files[0]
                
                # Read existing TXT
                with open(txt_file, 'r', encoding='utf-8') as f:
                    txt_content = f.read()
                
                # Insert location information after filename
                pattern = r'(Image:.*?\n)'
                insertion = f'Latitude: {latitude:.6f}\nLongitude: {longitude:.6f}\n'
                txt_content = re.sub(pattern, r'\1' + insertion, txt_content)
                
                # Save updated TXT
                with open(txt_file, 'w', encoding='utf-8') as f:
                    f.write(txt_content)
    except Exception as e:
        print(f"Error updating report with location: {e}")



def process_video(video_path):
    """Process video and detect potholes in frames"""
    if model is None:
        return None, "Model not loaded"
    
    try:
        file_name = Path(video_path).name
        
        cap = cv2.VideoCapture(video_path)
        
        if not cap.isOpened():
            return None, "Cannot open video"
        
        frame_width = int(cap.get(3))
        frame_height = int(cap.get(4))
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        total_detected_frames = 0
        total_potholes = 0
        frame_number = 0
        unique_pothole_ids = set()
        next_pothole_id = 1
        previous_centroids = {}
        distance_threshold = 50
        
        frame_detections = []
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            frame_number += 1
            current_centroids = {}
            
            try:
                results = model.predict(source=frame, conf=0.25, imgsz=640)
                result = results[0]
                pothole_count = len(result.boxes) if result.boxes is not None else 0
                
                if pothole_count > 0:
                    total_detected_frames += 1
                    total_potholes += pothole_count
                    
                    frame_det = {
                        'frame_number': frame_number,
                        'pothole_count': pothole_count,
                        'detections': []
                    }
                    
                    for i, box in enumerate(result.boxes, 1):
                        x1, y1, x2, y2 = box.xyxy[0]
                        cx = (x1 + x2) / 2
                        cy = (y1 + y2) / 2
                        current_centroids[i] = (cx, cy)
                        conf = box.conf.item()
                        
                        pothole_id = None
                        for prev_id, prev_centroid in previous_centroids.items():
                            distance = np.sqrt((cx - prev_centroid[0])**2 + (cy - prev_centroid[1])**2)
                            if distance < distance_threshold:
                                pothole_id = prev_id
                                break
                        
                        if pothole_id is None:
                            pothole_id = next_pothole_id
                            next_pothole_id += 1
                        
                        unique_pothole_ids.add(pothole_id)
                        
                        frame_det['detections'].append({
                            'pothole_id': pothole_id,
                            'confidence': f"{conf:.2%}",
                            'x1': int(x1),
                            'y1': int(y1),
                            'x2': int(x2),
                            'y2': int(y2)
                        })
                    
                    previous_centroids = current_centroids
                    frame_detections.append(frame_det)
                else:
                    previous_centroids = {}
            
            except Exception as e:
                print(f"Error processing frame {frame_number}: {e}")
        
        cap.release()
        
        # Build report
        report_data = {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'filename': file_name,
            'total_frames': total_frames,
            'fps': fps,
            'frames_with_detections': total_detected_frames,
            'total_potholes_detected': total_potholes,
            'unique_potholes': len(unique_pothole_ids),
            'frame_detections': frame_detections
        }
        
        # Build short report for JSON (without frame details)
        short_report_data = {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'filename': file_name,
            'total_frames': total_frames,
            'fps': fps,
            'frames_with_detections': total_detected_frames,
            'total_potholes_detected': total_potholes,
            'unique_potholes': len(unique_pothole_ids)
        }
        
        # Save report - use /tmp for Render compatibility
        report_dir = Path("/tmp/IN_vedio")
        report_dir.mkdir(exist_ok=True, parents=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Save short JSON (summary only)
        report_file_json = report_dir / f"video_report_{timestamp}.json"
        with open(report_file_json, 'w', encoding='utf-8') as rf:
            json.dump(short_report_data, rf, indent=2)
        
        # Save short summary report
        report_file_txt = report_dir / f"video_report_{timestamp}.txt"
        with open(report_file_txt, 'w', encoding='utf-8') as rf:
            rf.write("VIDEO POTHOLE DETECTION - SHORT REPORT\n")
            rf.write("=" * 50 + "\n\n")
            rf.write(f"Timestamp: {report_data['timestamp']}\n")
            rf.write(f"Video File: {file_name}\n")
            rf.write(f"Video FPS: {fps}\n")
            rf.write(f"Total Frames: {total_frames}\n\n")
            rf.write("DETECTION SUMMARY\n")
            rf.write("-" * 50 + "\n")
            rf.write(f"Frames with Detections: {total_detected_frames}\n")
            rf.write(f"Total Potholes Detected: {total_potholes}\n")
            rf.write(f"Unique Potholes: {len(unique_pothole_ids)}\n")
            rf.write("=" * 50 + "\n")
        
        # Save report to database
        save_report_to_db('video', file_name, short_report_data, str(report_file_txt))
        
        return {
            'success': True,
            'report': report_data,
            'report_file': str(report_file_txt)
        }, None
    
    except Exception as e:
        return None, str(e)


# Routes
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/upload-image', methods=['POST'])
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
def reports():
    """Get list of all reports from database"""
    # Fetch reports from database
    reports_data = get_reports_from_db()
    
    return jsonify(reports_data), 200


@app.route('/reports-stats')
def reports_stats():
    """Get database statistics"""
    stats = get_database_stats()
    return jsonify(stats), 200


@app.route('/report/<path:report_path>')
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
def download_report(report_path):
    """Download report file"""
    try:
        file_path = Path(report_path)
        if not file_path.exists():
            return jsonify({'error': 'Report not found'}), 404
        
        # Send file as attachment
        return send_file(
            str(file_path),
            as_attachment=True,
            download_name=file_path.name
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/start-camera-session', methods=['POST'])
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


@app.route('/detect-frame', methods=['POST'])
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
            results = model.predict(source=img, conf=0.25, imgsz=640, verbose=False)
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
            return jsonify({'success': False, 'error': f'Detection error: {str(model_error)}'}), 500
    
    except Exception as e:
        print(f"❌ General error in /detect-frame: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': f'Server error: {str(e)}'}), 500


@app.route('/save-camera-report', methods=['POST'])
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
        
        # Save report to database
        save_report_to_db('camera', None, data, str(report_file_txt))
        
        return jsonify({
            'success': True,
            'message': 'Report saved successfully',
            'report_file': str(report_file_txt)
        }), 200
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/save-location-with-report', methods=['POST'])
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


if __name__ == '__main__':
    # Initialize database on startup
    init_database()
    app.run(debug=True, host='0.0.0.0', port=5000)
