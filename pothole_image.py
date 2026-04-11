# Pothole Detection - Simple Image Upload
from pathlib import Path
import cv2
import matplotlib.pyplot as plt
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

def process_image(image_path):
    """Process image and detect potholes"""
    file_name = Path(image_path).name
    print(f"Processing: {file_name}\n")
    
    # Prediction
    results = model.predict(source=image_path, conf=0.2, imgsz=640)
    result = results[0]
    pothole_count = len(result.boxes) if result.boxes is not None else 0

    # Build report
    report_lines = []
    report_lines.append("=" * 60)
    report_lines.append("POTHOLE DETECTION REPORT")
    report_lines.append("=" * 60)
    report_lines.append(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append(f"Image: {file_name}")
    report_lines.append(f"Potholes Detected: {pothole_count}")
    report_lines.append("=" * 60)

    print("\n".join(report_lines))

    # Details
    if pothole_count > 0:
        report_lines.append("\nDetection Details:")
        report_lines.append("-" * 60)
        print("\nDetection Details:")
        print("-" * 60)

        for i, box in enumerate(result.boxes, 1):
            conf = box.conf.item()
            x1, y1, x2, y2 = box.xyxy[0]
            width = x2 - x1
            height = y2 - y1
            detail = f"Pothole {i}: Confidence = {conf:.2%}, Width = {width:.0f}px, Height = {height:.0f}px"
            report_lines.append(detail)
            print(detail)
    else:
        report_lines.append("\nNo potholes detected")
        print("No potholes detected")

    # Save report
    report_dir = Path("IN_image")
    report_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_file = report_dir / f"pothole_report_{timestamp}.txt"
    with open(report_file, 'w', encoding='utf-8') as rf:
        rf.write("\n".join(report_lines))
    
    print(f"\nReport saved to: {report_file}\n")

    # Display image with detections
    img = cv2.imread(image_path)

    if result.boxes is not None:
        for box in result.boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            conf = box.conf.item()
            cv2.rectangle(img, (x1, y1), (x2, y2), (0, 0, 255), 2)
            label = f"pothole {conf:.2f}"
            cv2.putText(img, label, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2, cv2.LINE_AA)

    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    plt.figure(figsize=(10, 8))
    plt.imshow(img)
    plt.axis("off")
    plt.title(f"Detection Results - {pothole_count} Pothole(s)")
    plt.tight_layout()
    plt.show()

# Simple file dialog
print("Select an image to detect potholes...")
root = tk.Tk()
root.withdraw()

file_path = filedialog.askopenfilename(
    title="Select Image",
    filetypes=[("Image files", "*.jpg *.jpeg *.png *.bmp"), ("All files", "*.*")]
)

if file_path:
    process_image(file_path)
else:
    print("No image selected.")