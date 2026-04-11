# Pothole Detection - Simple Video Upload
import cv2
import numpy as np
from pathlib import Path
from datetime import datetime
from ultralytics import YOLO
import tkinter as tk
from tkinter import filedialog

# Load YOLO model
model_path = Path("best.pt")
if not model_path.exists():
    print(f"⚠️ Model not found at {model_path.resolve()}")
    exit(1)

model = YOLO(str(model_path))
print(f"✓ Model loaded from {model_path}\n")

def process_video(video_path):
    """Process video and detect potholes in frames"""
    file_name = Path(video_path).name
    print(f"Processing: {file_name}\n")
    
    cap = cv2.VideoCapture(video_path)
    
    if not cap.isOpened():
        print("Error: Cannot open video")
        return
    
    # Video properties
    frame_width = int(cap.get(3))
    frame_height = int(cap.get(4))
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    # Report variables
    total_detected_frames = 0
    total_potholes = 0
    frame_number = 0
    unique_pothole_ids = set()
    next_pothole_id = 1
    previous_centroids = {}
    distance_threshold = 50  # pixels
    
    print(f"Total frames: {total_frames}, FPS: {fps}")
    print("Processing frames...\n")
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame_number += 1
        current_centroids = {}
        
        # Run YOLO prediction
        results = model.predict(source=frame, conf=0.2, imgsz=640, verbose=False)
        result = results[0]
        
        pothole_count = len(result.boxes) if result.boxes is not None else 0
        
        if pothole_count > 0:
            total_detected_frames += 1
            total_potholes += pothole_count
        
        # Track unique potholes
        if result.boxes is not None:
            for box in result.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                conf = box.conf.item()
                
                # Calculate centroid
                cx = (x1 + x2) // 2
                cy = (y1 + y2) // 2
                centroid = (cx, cy)
                
                # Match to previous detections
                matched = False
                for prev_id, prev_centroid in previous_centroids.items():
                    distance = np.sqrt((cx - prev_centroid[0])**2 + (cy - prev_centroid[1])**2)
                    if distance < distance_threshold:
                        pothole_id = prev_id
                        matched = True
                        break
                
                if not matched:
                    pothole_id = next_pothole_id
                    next_pothole_id += 1
                    unique_pothole_ids.add(pothole_id)
                
                current_centroids[pothole_id] = centroid
                
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
                label = f"ID:{pothole_id} {conf:.2f}"
                cv2.putText(frame, label, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2, cv2.LINE_AA)
        
        previous_centroids = current_centroids

        if frame_number % 30 == 0:
            progress = (frame_number / total_frames) * 100
            print(f"Progress: {progress:.1f}% ({frame_number}/{total_frames} frames)")
    
    cap.release()
    
    # Generate report
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_lines = []
    report_lines.append("=" * 60)
    report_lines.append("VIDEO POTHOLE DETECTION REPORT")
    report_lines.append("=" * 60)
    report_lines.append(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append(f"Video: {file_name}")
    report_lines.append(f"Total Frames: {total_frames}")
    report_lines.append(f"Frames with Potholes: {total_detected_frames}")
    report_lines.append(f"Unique Potholes: {len(unique_pothole_ids)}")
    if total_frames > 0:
        report_lines.append(f"Average per Frame: {total_potholes/total_frames:.2f}")
    report_lines.append("=" * 60)
    
    print("\n" + "\n".join(report_lines))
    
    # Save report
    report_dir = Path("IN_vedio")
    report_dir.mkdir(exist_ok=True)
    
    report_file = report_dir / f"video_report_{timestamp}.txt"
    with open(report_file, 'w', encoding='utf-8') as rf:
        rf.write("\n".join(report_lines))
    
    print(f"\nReport saved to: {report_file}\n")

# Simple file dialog
print("Select a video to detect potholes...")
root = tk.Tk()
root.withdraw()

file_path = filedialog.askopenfilename(
    title="Select Video",
    filetypes=[("Video files", "*.mp4 *.avi *.mov *.mkv"), ("All files", "*.*")]
)

if file_path:
    process_video(file_path)
else:
    print("No video selected.")