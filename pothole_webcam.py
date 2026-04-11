import cv2
import time
import numpy as np
from pathlib import Path
from datetime import datetime
from ultralytics import YOLO

model_path = Path("best.pt")

# Load and predict
model = YOLO(str(model_path))
cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("Error: Cannot access webcam")
    exit()

frame_width = int(cap.get(3))
frame_height = int(cap.get(4))

out = cv2.VideoWriter(
    "output.avi",
    cv2.VideoWriter_fourcc(*'XVID'),
    20,
    (frame_width, frame_height)
)

#Report variables

total_detected_frames = 0
frame_number = 0

# Unique pothole tracking
unique_pothole_ids = set()
next_pothole_id = 1
previous_centroids = {}
distance_threshold = 50  # pixels

print("Press 'q' to stop and see report...")

while True:
    ret, frame = cap.read()
    if not ret:
        break

    frame_number += 1
    current_centroids = {}

    try:
        results = model.predict(source=frame, conf=0.25, imgsz=640)
        result = results[0]

        count = len(result.boxes) if result.boxes is not None else 0

        # 🔥 Update report data
        if count > 0:
            total_detected_frames += 1
        

        #Draw boxes and track unique potholes
        if result.boxes is not None:
            for box in result.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                conf = box.conf.item()

                # Calculate centroid
                cx = (x1 + x2) // 2
                cy = (y1 + y2) // 2
                centroid = (cx, cy)

                # 🆔 Match to previous detections
                matched = False
                for prev_id, prev_centroid in previous_centroids.items():
                    distance = np.sqrt((cx - prev_centroid[0])**2 + (cy - prev_centroid[1])**2)
                    if distance < distance_threshold:
                        # Same pothole detected again
                        pothole_id = prev_id
                        matched = True
                        break

                if not matched:
                    # unique pothole
                    pothole_id = next_pothole_id
                    next_pothole_id += 1
                    unique_pothole_ids.add(pothole_id)

                current_centroids[pothole_id] = centroid

                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)

                label = f"ID:{pothole_id} {conf:.2f}"
                cv2.putText(frame, label, (x1, y1 - 5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                            (0, 0, 255), 1, cv2.LINE_AA)

        # Update previous centroids for next frame
        previous_centroids = current_centroids

        # 🔢 Live count
        cv2.putText(frame, f"Current: {count} | Unique: {len(unique_pothole_ids)}", (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

        # 💾 Save image
        # if count > 0:
        #     cv2.imwrite(f"detected_{int(time.time())}.jpg", frame)

        # 🎥 Save video
        out.write(frame)

        cv2.imshow("Live Pothole Detection", frame)

    except Exception as e:
        print(f"Error: {e}")

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# 🔹 Release
cap.release()
out.release()
cv2.destroyAllWindows()

# =========================
# 📊 FINAL REPORT
# =========================
report_lines = [
    "="*50,
    "FINAL POTHOLE DETECTION REPORT",
    "="*50,
    f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
    f"Total Frames Processed: {frame_number}",
    f"Unique Potholes in Session: {len(unique_pothole_ids)}",
    f"Frames with Potholes: {total_detected_frames}",
    "Potholes were detected in this session." if total_detected_frames > 0 else "No potholes detected.",
    "="*50
]

print("\n" + "\n".join(report_lines))

report_file = Path(f"IN_cam/live_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
with open(report_file, "w", encoding="utf-8") as f:
    f.write("\n".join(report_lines))

print(f"Report saved to: {report_file.resolve()}")