import os
import gc
import json
import base64
import re
import cv2
import numpy as np
import torch
from pathlib import Path
from datetime import datetime
from ultralytics import YOLO

# Configure YOLO cache directory
os.environ['YOLO_CONFIG_DIR'] = '/tmp/Ultralytics'
os.environ['YOLO_CACHE'] = '/tmp/yolo_cache'
os.environ['ULTRALYTICS_SKIP_UPDATE'] = 'true'

# Import database function
try:
    from database import save_report_to_db
except ImportError:
    # Fallback if database module is not available
    def save_report_to_db(category, filename, report_data, report_file):
        pass

# Global model variable - lazy loaded on first use
_model = None
_model_loaded = False

def get_model():
    """Lazy load YOLO model on first use - reduces startup memory
    
    Tries to use ONNX model first (50-100MB) for memory efficiency,
    falls back to PyTorch if ONNX not available (300MB)
    """
    global _model, _model_loaded
    
    if _model_loaded:
        return _model
    
    _model_loaded = True
    
    try:
        # Try to load ONNX model first (smallest)
        if os.path.exists('best.onnx'):
            print("Loading YOLO model from best.onnx (ONNX - optimized)...")
            _model = YOLO('best.onnx')
            print("✅ ONNX model loaded successfully (50-100 MB)")
        elif os.path.exists('best(2).onnx'):
            print("Loading YOLO model from best(2).onnx (ONNX - optimized)...")
            _model = YOLO('best(2).onnx')
            print("✅ ONNX model loaded successfully (50-100 MB)")
        # Fall back to PyTorch if ONNX not available
        elif os.path.exists('best.pt'):
            print("Loading YOLO model from best.pt (PyTorch)...")
            _model = YOLO('best.pt')
            print("⚠️  PyTorch model loaded (300 MB). Consider converting to ONNX!")
        elif os.path.exists('best(2).pt'):
            print("Loading YOLO model from best(2).pt (PyTorch)...")
            _model = YOLO('best(2).pt')
            print("⚠️  PyTorch model loaded (300 MB). Consider converting to ONNX!")
        else:
            _model = None
            print("❌ Error: No model file found (best.pt, best.onnx, best(2).pt, or best(2).onnx)")
    except Exception as e:
        _model = None
        print(f"❌ Error loading YOLO model: {e}")
    
    return _model

# Keep 'model' variable for backward compatibility with app.py imports
model = None


def process_image(image_path):
    """Process image and detect potholes (memory-optimized with streaming)"""
    model = get_model()
    if model is None:
        return None, "Model not loaded"
    
    try:
        file_name = Path(image_path).name
        
        # OPTIMIZATION 1: Stream image - load with reduced resolution first
        img_original = cv2.imread(image_path)
        if img_original is None:
            return None, f"Failed to load image: {image_path}"
        
        # Get original dimensions for later scaling
        orig_height, orig_width = img_original.shape[:2]
        
        # OPTIMIZATION 2: Reduce image resolution to save memory during inference
        # Max size 416x416 (matches imgsz), aspect ratio preserved
        max_dim = 416
        if orig_width > max_dim or orig_height > max_dim:
            scale = min(max_dim / orig_width, max_dim / orig_height)
            new_width = int(orig_width * scale)
            new_height = int(orig_height * scale)
            img_inference = cv2.resize(img_original, (new_width, new_height), interpolation=cv2.INTER_AREA)
            print(f"📸 Image resized: {orig_width}x{orig_height} → {new_width}x{new_height} (memory optimized)")
        else:
            img_inference = img_original
        
        # Prediction with optimized parameters
        results = model.predict(
            source=img_inference, 
            conf=0.2, 
            imgsz=416,
            verbose=False,
            device='cpu'  # CPU only for deployment
        )
        result = results[0]
        pothole_count = len(result.boxes) if result.boxes is not None else 0

        # Build report
        report_data = {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'filename': file_name,
            'pothole_count': pothole_count,
            'detections': []
        }

        # Get detection details - scale coordinates back to original size
        if pothole_count > 0:
            scale_x = orig_width / img_inference.shape[1]
            scale_y = orig_height / img_inference.shape[0]
            
            for i, box in enumerate(result.boxes, 1):
                conf = box.conf.item()
                x1, y1, x2, y2 = box.xyxy[0]
                # Scale back to original image coordinates
                x1, y1, x2, y2 = x1 * scale_x, y1 * scale_y, x2 * scale_x, y2 * scale_y
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

        # OPTIMIZATION 3: Draw boxes on original image for annotation
        img_annotated = img_original.copy()
        
        # Draw bounding boxes on detected potholes
        if result.boxes is not None and len(result.boxes) > 0:
            scale_x = orig_width / img_inference.shape[1]
            scale_y = orig_height / img_inference.shape[0]
            
            for box in result.boxes:
                x1, y1, x2, y2 = box.xyxy[0]
                # Scale to original coordinates
                x1, y1, x2, y2 = int(x1 * scale_x), int(y1 * scale_y), int(x2 * scale_x), int(y2 * scale_y)
                conf = box.conf.item()
                
                # Draw rectangle with bright cyan color
                cv2.rectangle(img_annotated, (x1, y1), (x2, y2), (0, 255, 255), 3)
                
                # Draw filled background for text
                label = f"Pothole: {conf:.2%}"
                text_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
                cv2.rectangle(img_annotated, (x1, y1 - text_size[1] - 8), (x1 + text_size[0] + 4, y1), (0, 255, 255), -1)
                
                # Put text
                cv2.putText(img_annotated, label, (x1 + 2, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)

        # Save annotated image with compression
        output_path = report_dir / f"annotated_{timestamp}.jpg"
        cv2.imwrite(str(output_path), img_annotated, [cv2.IMWRITE_JPEG_QUALITY, 85])

        # Convert to base64 for display (stream conversion to avoid memory spike)
        _, buffer = cv2.imencode('.jpg', img_annotated, [cv2.IMWRITE_JPEG_QUALITY, 85])
        img_base64 = base64.b64encode(buffer).decode('utf-8')

        # Save report to database
        save_report_to_db('image', file_name, report_data, str(report_file_txt))

        # Clean up memory aggressively
        del img_original, img_inference, img_annotated, buffer, result, results
        gc.collect()

        return {
            'success': True,
            'report': report_data,
            'image_base64': img_base64,
            'report_file': str(report_file_txt)
        }, None

    except Exception as e:
        gc.collect()
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
    """Process video and detect potholes in frames (memory-optimized streaming)"""
    model = get_model()
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
        frame_skip = max(1, fps // 10)  # Process every Nth frame to save memory
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            frame_number += 1
            
            # Skip frames for faster processing
            if frame_number % frame_skip != 0:
                continue
            
            # OPTIMIZATION: Reduce frame size for inference (keep aspect ratio)
            h, w = frame.shape[:2]
            
            # Stream optimization: Only keep reduced-size frame in memory
            max_dim = 384  # Smaller than image for video efficiency
            if w > max_dim or h > max_dim:
                scale = min(max_dim / w, max_dim / h)
                new_w = int(w * scale)
                new_h = int(h * scale)
                frame_resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
                scale_factor = scale
            else:
                frame_resized = frame
                scale_factor = 1.0
            
            current_centroids = {}
            
            try:
                results = model.predict(
                    source=frame_resized, 
                    conf=0.25, 
                    imgsz=384,  # Optimized size
                    verbose=False,
                    device='cpu'  # CPU only
                )
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
                        # Scale back to original size
                        x1, y1, x2, y2 = x1/scale_factor, y1/scale_factor, x2/scale_factor, y2/scale_factor
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
            
            finally:
                # Clean up frame memory immediately (streaming)
                del frame_resized
                if frame_number % 100 == 0:
                    gc.collect()
        
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
        
        # Clean up memory
        del frame, cap
        gc.collect()
        
        return {
            'success': True,
            'report': report_data,
            'report_file': str(report_file_txt)
        }, None
    
    except Exception as e:
        return None, str(e)
