from flask import Blueprint, jsonify, request
from pathlib import Path
from datetime import datetime
import json

from auth_utils import login_required
from database import save_report_to_db, save_report_file

bp = Blueprint("report_save", __name__)


@bp.route("/save-camera-report", methods=["POST"])
@login_required
def save_camera_report():
    """Save camera detection report"""
    try:
        data = request.json or {}

        report_dir = Path("IN_cam")
        report_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        lat = data.get("latitude")
        lng = data.get("longitude")
        pothole_locations = data.get("pothole_locations", {})

        if (lat is None or lng is None) and pothole_locations:
            try:
                first_p = list(pothole_locations.values())[0]
                if isinstance(first_p, dict):
                    lat = first_p.get("lat", first_p.get("latitude"))
                    lng = first_p.get("lng", first_p.get("longitude"))
            except Exception:
                pass

        if lat is not None and lng is not None:
            data["latitude"] = float(lat)
            data["longitude"] = float(lng)

        report_file_json = report_dir / f"live_report_{timestamp}.json"
        with open(report_file_json, "w", encoding="utf-8") as rf:
            json.dump(data, rf, indent=2)

        report_file_txt = report_dir / f"live_report_{timestamp}.txt"
        with open(report_file_txt, "w", encoding="utf-8") as rf:
            rf.write("LIVE CAMERA DETECTION - INSPECTION REPORT\n")
            rf.write("=" * 50 + "\n\n")
            rf.write(f"Timestamp: {data.get('timestamp', 'N/A')}\n")
            rf.write(f"Runtime:   {data.get('runtime_seconds', 0)} seconds\n\n")
            rf.write("DETECTION SUMMARY\n")
            rf.write("-" * 50 + "\n")
            rf.write(f"Total Detections: {data.get('total_detections', 0)}\n")
            rf.write(f"Unique Potholes:  {data.get('unique_potholes', 0)}\n")

            if lat is not None and lng is not None:
                rf.write("\nLOCATION\n")
                rf.write("-" * 50 + "\n")
                rf.write(f"Latitude:  {float(lat):.6f}\n")
                rf.write(f"Longitude: {float(lng):.6f}\n")

            if pothole_locations:
                rf.write("\n" + "=" * 50 + "\n")
                rf.write("DETECTED POTHOLE INCIDENTS & COORDINATES\n")
                rf.write("=" * 50 + "\n")
                for pothole_id, location_info in sorted(pothole_locations.items()):
                    if isinstance(location_info, dict):
                        p_lat = location_info.get("lat", location_info.get("latitude", "N/A"))
                        p_lng = location_info.get("lng", location_info.get("longitude", "N/A"))
                        p_time = location_info.get("timestamp", "N/A")
                        rf.write(f"\nPothole #{pothole_id}:\n")
                        rf.write(f"  Latitude:  {p_lat}\n")
                        rf.write(f"  Longitude: {p_lng}\n")
                        rf.write(f"  Time:      {p_time}\n")

            rf.write("\n" + "=" * 50 + "\n")

        report_id = save_report_to_db("camera", None, data, str(report_file_txt))
        try:
            if report_id:
                with open(report_file_txt, "rb") as f:
                    content_bytes = f.read()
                save_report_file(report_id, report_file_txt.name, content_bytes, mime_type="text/plain")
        except Exception as e:
            print(f"Failed to save report blob to DB: {e}")

        return jsonify({
            "success": True,
            "message": "Report saved successfully",
            "report_file": str(report_file_txt),
            "report_id": report_id
        }), 200

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route("/save-location-with-report", methods=["POST"])
@login_required
def save_location_with_report():
    """Save location data with the detection report"""
    try:
        data = request.get_json() or {}
        report = data.get("report") or {}

        location = data.get("location")
        if not location or not isinstance(location, dict):
            lat_val = data.get("latitude", data.get("lat"))
            lng_val = data.get("longitude", data.get("lng"))
            if lat_val is not None and lng_val is not None:
                location = {"lat": float(lat_val), "lng": float(lng_val)}

        if not location:
            return jsonify({"success": False, "error": "No location data provided"}), 400

        try:
            lat = float(location.get("lat") if location.get("lat") is not None else location.get("latitude", 0))
            lng = float(location.get("lng") if location.get("lng") is not None else location.get("longitude", 0))
        except (ValueError, TypeError):
            return jsonify({"success": False, "error": "Invalid latitude or longitude format"}), 400

        report["location"] = {"latitude": lat, "longitude": lng}

        search_dirs = [
            Path("IN_image"),
            Path("/tmp/IN_image"),
            Path("C:/tmp/IN_image"),
            Path.cwd() / "IN_image"
        ]

        report_files = []
        for d in search_dirs:
            if d.exists():
                try:
                    report_files.extend(list(d.glob("pothole_report_*.json")))
                except Exception:
                    pass

        report_files.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)

        if report_files:
            latest_report_file = report_files[0]
            try:
                with open(latest_report_file, "r", encoding="utf-8") as f:
                    existing_report = json.load(f)
                existing_report["location"] = {"latitude": lat, "longitude": lng}
                with open(latest_report_file, "w", encoding="utf-8") as f:
                    json.dump(existing_report, f, indent=2)
            except Exception as e:
                print(f"Error updating report json: {e}")

            latest_txt = latest_report_file.with_suffix(".txt")
            if latest_txt.exists():
                try:
                    with open(latest_txt, "r", encoding="utf-8") as f:
                        txt_content = f.read()
                    import re
                    if "Latitude:" not in txt_content:
                        txt_content = re.sub(r"(Image:.*?\n)", r"\1" + f"Latitude: {lat:.6f}\nLongitude: {lng:.6f}\n", txt_content)
                    else:
                        txt_content = re.sub(r"Latitude:\s*[-+]?\d+(?:\.\d+)?", f"Latitude: {lat:.6f}", txt_content)
                        txt_content = re.sub(r"Longitude:\s*[-+]?\d+(?:\.\d+)?", f"Longitude: {lng:.6f}", txt_content)
                    with open(latest_txt, "w", encoding="utf-8") as f:
                        f.write(txt_content)
                except Exception as e:
                    print(f"Error updating report txt: {e}")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        location_dir = Path("IN_image/locations")
        location_dir.mkdir(parents=True, exist_ok=True)

        filename = report.get("filename")
        if not filename and report_files:
            try:
                with open(report_files[0], "r", encoding="utf-8") as rf:
                    filename = json.load(rf).get("filename")
            except Exception:
                pass

        location_data = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "filename": filename or "image_upload.jpg",
            "latitude": lat,
            "longitude": lng,
            "pothole_count": report.get("pothole_count", 0),
            "detections": report.get("detections", [])
        }

        location_file = location_dir / f"location_report_{timestamp}.json"
        with open(location_file, "w", encoding="utf-8") as f:
            json.dump(location_data, f, indent=2)

        txt_file = location_dir / f"location_report_{timestamp}.txt"
        with open(txt_file, "w", encoding="utf-8") as f:
            f.write("=" * 60 + "\n")
            f.write("POTHOLE DETECTION REPORT WITH LOCATION\n")
            f.write("=" * 60 + "\n")
            f.write(f"Timestamp: {location_data['timestamp']}\n")
            f.write(f"Image: {location_data['filename']}\n")
            f.write(f"Latitude: {location_data['latitude']:.6f}\n")
            f.write(f"Longitude: {location_data['longitude']:.6f}\n")
            f.write(f"Potholes Detected: {location_data['pothole_count']}\n")
            f.write("=" * 60 + "\n")
            if location_data["detections"]:
                f.write("\nDetection Details:\n")
                f.write("-" * 60 + "\n")
                for det in location_data["detections"]:
                    f.write(f"Pothole {det.get('pothole_id')}: Confidence = {det.get('confidence')}, Width = {det.get('width_px')}px, Height = {det.get('height_px')}px\n")
            else:
                f.write("\nNo potholes detected\n")

        try:
            from database import sqlite3, DATABASE
            conn = sqlite3.connect(DATABASE)
            c = conn.cursor()
            report_id = data.get("report_id")
            if not report_id:
                c.execute("SELECT id FROM reports WHERE report_type = 'image' ORDER BY id DESC LIMIT 1")
                row = c.fetchone()
                if row:
                    report_id = row[0]
            if report_id:
                c.execute("UPDATE reports SET latitude = ?, longitude = ? WHERE id = ?", (lat, lng, report_id))
                conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error updating SQLite location: {e}")

        return jsonify({
            "success": True,
            "message": "Location saved successfully",
            "latitude": lat,
            "longitude": lng,
            "location_file": str(location_file)
        }), 200

    except Exception as e:
        print(f"Error in save_location_with_report: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route("/save-video-location-with-report", methods=["POST"])
@login_required
def save_video_location_with_report():
    """Save location data with the video detection report"""
    try:
        data = request.get_json() or {}
        report = data.get("report") or {}

        location = data.get("location")
        if not location or not isinstance(location, dict):
            lat_val = data.get("latitude", data.get("lat"))
            lng_val = data.get("longitude", data.get("lng"))
            if lat_val is not None and lng_val is not None:
                location = {"lat": float(lat_val), "lng": float(lng_val)}

        if not location:
            return jsonify({"success": False, "error": "No location data provided"}), 400

        try:
            lat = float(location.get("lat") if location.get("lat") is not None else location.get("latitude", 0))
            lng = float(location.get("lng") if location.get("lng") is not None else location.get("longitude", 0))
        except (ValueError, TypeError):
            return jsonify({"success": False, "error": "Invalid latitude or longitude format"}), 400

        report["location"] = {"latitude": lat, "longitude": lng}

        search_dirs = [
            Path("IN_vedio"),
            Path("/tmp/IN_vedio"),
            Path("C:/tmp/IN_vedio"),
            Path.cwd() / "IN_vedio"
        ]

        report_files = []
        for d in search_dirs:
            if d.exists():
                try:
                    report_files.extend(list(d.glob("video_report_*.json")))
                except Exception:
                    pass

        report_files.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)

        if report_files:
            latest_report_file = report_files[0]
            try:
                with open(latest_report_file, "r", encoding="utf-8") as f:
                    existing_report = json.load(f)
                existing_report["location"] = {"latitude": lat, "longitude": lng}
                with open(latest_report_file, "w", encoding="utf-8") as f:
                    json.dump(existing_report, f, indent=2)
            except Exception as e:
                print(f"Error updating video report json: {e}")

            latest_txt = latest_report_file.with_suffix(".txt")
            if latest_txt.exists():
                try:
                    with open(latest_txt, "r", encoding="utf-8") as f:
                        txt_content = f.read()
                    import re
                    if "Latitude:" not in txt_content:
                        txt_content = re.sub(r"(Total Frames:.*?\n)", r"\1" + f"Latitude: {lat:.6f}\nLongitude: {lng:.6f}\n", txt_content)
                    else:
                        txt_content = re.sub(r"Latitude:\s*[-+]?\d+(?:\.\d+)?", f"Latitude: {lat:.6f}", txt_content)
                        txt_content = re.sub(r"Longitude:\s*[-+]?\d+(?:\.\d+)?", f"Longitude: {lng:.6f}", txt_content)
                    with open(latest_txt, "w", encoding="utf-8") as f:
                        f.write(txt_content)
                except Exception as e:
                    print(f"Error updating video report txt: {e}")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        location_dir = Path("IN_vedio/locations")
        location_dir.mkdir(parents=True, exist_ok=True)

        location_data = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "filename": report.get("filename") or "video_upload.mp4",
            "latitude": lat,
            "longitude": lng,
            "total_frames": report.get("total_frames", 0),
            "total_potholes_detected": report.get("total_potholes_detected", 0),
            "unique_potholes": report.get("unique_potholes", 0)
        }

        location_file = location_dir / f"video_location_report_{timestamp}.json"
        with open(location_file, "w", encoding="utf-8") as f:
            json.dump(location_data, f, indent=2)

        txt_file = location_dir / f"video_location_report_{timestamp}.txt"
        with open(txt_file, "w", encoding="utf-8") as f:
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

        try:
            from database import sqlite3, DATABASE
            conn = sqlite3.connect(DATABASE)
            c = conn.cursor()
            report_id = data.get("report_id")
            if not report_id:
                c.execute("SELECT id FROM reports WHERE report_type = 'video' ORDER BY id DESC LIMIT 1")
                row = c.fetchone()
                if row:
                    report_id = row[0]
            if report_id:
                c.execute("UPDATE reports SET latitude = ?, longitude = ? WHERE id = ?", (lat, lng, report_id))
                conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error updating SQLite video location: {e}")

        return jsonify({
            "success": True,
            "message": "Video location saved successfully",
            "latitude": lat,
            "longitude": lng,
            "location_file": str(location_file)
        }), 200

    except Exception as e:
        print(f"Error in save_video_location_with_report: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
