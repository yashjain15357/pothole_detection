import React, { useState, useRef } from 'react';
import { 
  Upload, 
  Camera, 
  CheckCircle, 
  AlertCircle, 
  MapPin, 
  Save, 
  RefreshCw,
  Eye,
  Navigation
} from 'lucide-react';
import LeafletMapPicker from './LeafletMapPicker';
import { apiUrl, safeFetchJson } from '../apiConfig';

export default function ImageDetectionTab({ onToast, user }) {
  const [selectedFile, setSelectedFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState(null);

  // Camera capture modal state
  const [cameraModalOpen, setCameraModalOpen] = useState(false);
  const [capturedBlob, setCapturedBlob] = useState(null);
  const [cameraStream, setCameraStream] = useState(null);
  const videoRef = useRef(null);
  const canvasRef = useRef(null);

  // Customizable Map location state (Default: Bhopal/Central India or user chosen)
  const [latitude, setLatitude] = useState(23.5183);
  const [longitude, setLongitude] = useState(77.8128);
  const [savingLocation, setSavingLocation] = useState(false);
  const [locationSaved, setLocationSaved] = useState(false);

  // Handle file select
  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      setSelectedFile(file);
      setError('');
    }
  };

  // Upload image to /upload-image
  const processImageFile = async (fileToUpload) => {
    setLoading(true);
    setError('');
    setResult(null);
    setLocationSaved(false);

    const formData = new FormData();
    formData.append('file', fileToUpload);
    formData.append('latitude', latitude);
    formData.append('longitude', longitude);

    try {
      const { response, data } = await safeFetchJson(apiUrl('/upload-image'), {
        method: 'POST',
        credentials: 'include',
        body: formData,
      });

      if (response.ok && data.success !== false) {
        // Ensure location is tracked
        if (data.report && !data.report.location) {
          data.report.location = { latitude, longitude };
        }
        setResult(data);
        onToast('Image analyzed! You can now adjust or confirm the road location.', 'success');
      } else {
        setError(data.error || 'Failed to detect potholes in image');
      }
    } catch (err) {
      setError('Error communicating with the detection server: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  // Open Webcam Modal
  const openCamera = async () => {
    setCameraModalOpen(true);
    setCapturedBlob(null);
    setError('');

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'environment' }
      });
      setCameraStream(stream);
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
      }
    } catch (err) {
      setError('Cannot access camera: ' + err.message);
      setCameraModalOpen(false);
    }
  };

  const closeCamera = () => {
    if (cameraStream) {
      cameraStream.getTracks().forEach((track) => track.stop());
      setCameraStream(null);
    }
    setCameraModalOpen(false);
  };

  const snapPhoto = () => {
    if (!videoRef.current || !canvasRef.current) return;
    const video = videoRef.current;
    const canvas = canvasRef.current;
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    canvas.toBlob((blob) => {
      setCapturedBlob(blob);
    }, 'image/jpeg', 0.95);
  };

  const confirmCapturedPhoto = () => {
    if (!capturedBlob) return;
    const file = new File([capturedBlob], 'captured_image.jpg', { type: 'image/jpeg' });
    setSelectedFile(file);
    closeCamera();
    processImageFile(file);
  };

  // Save/Update location to report
  const handleSaveLocation = async () => {
    setSavingLocation(true);
    try {
      const payload = {
        report: result?.report || {},
        report_id: result?.report?.id,
        location: {
          lat: Number(latitude),
          lng: Number(longitude)
        },
        latitude: Number(latitude),
        longitude: Number(longitude),
      };

      const { response: res, data } = await safeFetchJson(apiUrl('/save-location-with-report'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(payload),
      });
      if (res.ok && data.success) {
        setLocationSaved(true);
        if (result && result.report) {
          result.report.location = {
            latitude: Number(latitude),
            longitude: Number(longitude)
          };
        }
        onToast('Geotag pinned to the pothole report successfully!', 'success');
      } else {
        onToast(data.error || 'Failed to save location', 'error');
      }
    } catch (err) {
      onToast('Error saving location: ' + err.message, 'error');
    } finally {
      setSavingLocation(false);
    }
  };

  if (!user) {
    return (
      <div style={{ padding: '32px 0' }}>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '14px',
          padding: '18px 20px',
          borderRadius: '12px',
          background: '#fef2f2',
          border: '1px solid #fca5a5',
          color: '#b91c1c',
          fontWeight: 700,
          fontSize: '1.1rem'
        }}>
          <AlertCircle size={28} />
          Authentication required. Please log in to upload and analyze images.
        </div>
      </div>
    );
  }

  return (
    <div>
      <div style={{ marginBottom: '24px' }}>
        <h2 style={{ fontSize: '1.5rem', fontWeight: 800, color: '#0f172a' }}>Pothole Image Detection</h2>
        <p style={{ color: '#64748b', fontSize: '0.9rem' }}>
          Upload road photos or snap live conditions, then pin or customize the road coordinates on the interactive map.
        </p>
      </div>

      {error && (
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '10px',
          background: '#fef2f2',
          border: '1px solid #fecaca',
          color: '#b91c1c',
          padding: '14px',
          borderRadius: '8px',
          marginBottom: '20px'
        }}>
          <AlertCircle size={20} />
          <span>{error}</span>
        </div>
      )}

      {/* Input Selector Area */}
      {!result && (
        <div className="card" style={{ marginBottom: '24px' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
            {/* File Upload Dropzone */}
            <div
              className="dropzone"
              onClick={() => document.getElementById('image-file-input').click()}
            >
              <input
                id="image-file-input"
                type="file"
                accept="image/*"
                onChange={handleFileChange}
                style={{ display: 'none' }}
              />
              <Upload className="dropzone-icon" />
              <h3 style={{ fontSize: '1rem', fontWeight: 700, color: '#1e293b', marginBottom: '4px' }}>
                {selectedFile ? selectedFile.name : 'Choose Road Image File'}
              </h3>
              <p style={{ fontSize: '0.8rem', color: '#64748b' }}>
                Supports JPG, PNG, WEBP, BMP up to 500MB
              </p>
              {selectedFile && (
                <div style={{ marginTop: '16px' }}>
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      processImageFile(selectedFile);
                    }}
                    disabled={loading}
                    className="btn btn-primary"
                  >
                    {loading ? <div className="spinner" /> : <><Eye size={16} /> Analyze with YOLO</>}
                  </button>
                </div>
              )}
            </div>

            {/* Webcam Snapshot Option */}
            <div
              className="dropzone"
              onClick={openCamera}
              style={{ background: '#f0fdf4', borderColor: '#bbf7d0' }}
            >
              <Camera className="dropzone-icon" style={{ color: '#16a34a' }} />
              <h3 style={{ fontSize: '1rem', fontWeight: 700, color: '#1e293b', marginBottom: '4px' }}>
                Capture from Device Camera
              </h3>
              <p style={{ fontSize: '0.8rem', color: '#64748b' }}>
                Take an on-site photo with your camera
              </p>
              <div style={{ marginTop: '16px' }}>
                <button type="button" className="btn btn-success">
                  <Camera size={16} /> Open Camera
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Inference Results Section */}
      {result && (
        <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: '24px' }}>
          {/* Annotated Image & Detections */}
          <div className="card">
            <div className="card-header">
              <h3 className="card-title">
                <CheckCircle size={20} color="#10b981" />
                Detection Output ({result.report?.pothole_count || 0} Found)
              </h3>
              <button
                onClick={() => {
                  setResult(null);
                  setSelectedFile(null);
                }}
                className="btn btn-secondary"
                style={{ padding: '6px 12px', fontSize: '0.8rem' }}
              >
                <RefreshCw size={14} /> Scan Another
              </button>
            </div>

            <div style={{
              borderRadius: '10px',
              overflow: 'hidden',
              background: '#0f172a',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              maxHeight: '400px',
              marginBottom: '16px'
            }}>
              <img
                src={`data:image/jpeg;base64,${result.image_base64}`}
                alt="Detected Potholes"
                style={{ maxWidth: '100%', maxHeight: '400px', objectFit: 'contain' }}
              />
            </div>

            {/* Current Geotag Display */}
            <div style={{
              background: '#e0f2fe',
              border: '1px solid #bae6fd',
              borderRadius: '8px',
              padding: '10px 14px',
              marginBottom: '16px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <MapPin size={18} color="#0284c7" />
                <div>
                  <span style={{ fontSize: '0.75rem', fontWeight: 700, color: '#0369a1', textTransform: 'uppercase' }}>
                    Report Geotag Coordinates:
                  </span>
                  <p style={{ fontSize: '0.9rem', fontWeight: 700, color: '#0c4a6e' }}>
                    {Number(latitude).toFixed(6)}, {Number(longitude).toFixed(6)}
                  </p>
                </div>
              </div>
              <span className="badge" style={{ background: locationSaved ? '#dcfce7' : '#fef9c3', color: locationSaved ? '#15803d' : '#854d0e' }}>
                {locationSaved ? '✓ Geotag Saved' : '● Unsaved Changes'}
              </span>
            </div>

            {/* Detections List */}
            <div>
              <h4 style={{ fontSize: '0.9rem', fontWeight: 700, color: '#334155', marginBottom: '8px' }}>
                Bounding Box Metrics:
              </h4>
              <div className="table-responsive" style={{ maxHeight: '160px', overflowY: 'auto' }}>
                <table>
                  <thead>
                    <tr>
                      <th>#</th>
                      <th>Confidence</th>
                      <th>Dimensions</th>
                      <th>Location Bounds</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(result.report?.detections || []).map((det) => (
                      <tr key={det.pothole_id}>
                        <td><strong>#{det.pothole_id}</strong></td>
                        <td>
                          <span style={{ color: '#4f46e5', fontWeight: 700 }}>
                            {det.confidence}
                          </span>
                        </td>
                        <td>{det.width_px} × {det.height_px} px</td>
                        <td style={{ fontSize: '0.8rem', color: '#64748b' }}>
                          ({det.x1}, {det.y1}) to ({det.x2}, {det.y2})
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          {/* Location Picker & Geotagging */}
          <div className="card">
            <div className="card-header">
              <h3 className="card-title">
                <MapPin size={20} color="#06b6d4" />
                Customize Road Location Pin
              </h3>
            </div>

            <p style={{ fontSize: '0.85rem', color: '#64748b', marginBottom: '12px' }}>
              Drag the marker or click anywhere on the map to set the exact street location of the pothole. You can also enter manual coordinates below.
            </p>

            <LeafletMapPicker
              latitude={latitude}
              longitude={longitude}
              onLocationChange={(lat, lng) => {
                setLatitude(lat);
                setLongitude(lng);
                setLocationSaved(false);
              }}
              height="280px"
            />

            <div style={{ marginTop: '16px' }}>
              <button
                type="button"
                onClick={handleSaveLocation}
                disabled={savingLocation}
                className="btn btn-primary"
                style={{
                  width: '100%',
                  padding: '12px',
                  background: locationSaved ? '#10b981' : '#4f46e5'
                }}
              >
                {savingLocation ? (
                  <div className="spinner" />
                ) : (
                  <><Save size={16} /> {locationSaved ? 'Geotag Saved! (Click to Update)' : 'Confirm & Save Geotag to Report'}</>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Camera Capture Modal */}
      {cameraModalOpen && (
        <div className="modal-overlay">
          <div className="modal-dialog">
            <div className="modal-header">
              <h3 style={{ fontSize: '1.1rem', fontWeight: 700 }}>Device Camera Snapshot</h3>
              <button onClick={closeCamera} style={{ border: 'none', background: 'transparent', cursor: 'pointer', fontSize: '1.2rem' }}>
                ✕
              </button>
            </div>

            <div className="modal-body" style={{ textAlign: 'center' }}>
              {!capturedBlob ? (
                <div>
                  <video
                    ref={videoRef}
                    autoPlay
                    playsInline
                    style={{
                      width: '100%',
                      maxHeight: '360px',
                      borderRadius: '8px',
                      background: '#000',
                      objectFit: 'cover'
                    }}
                  />
                  <canvas ref={canvasRef} style={{ display: 'none' }} />
                </div>
              ) : (
                <div>
                  <img
                    src={URL.createObjectURL(capturedBlob)}
                    alt="Captured snapshot"
                    style={{ width: '100%', maxHeight: '360px', borderRadius: '8px' }}
                  />
                </div>
              )}
            </div>

            <div className="modal-footer">
              {!capturedBlob ? (
                <>
                  <button onClick={closeCamera} className="btn btn-secondary">Cancel</button>
                  <button onClick={snapPhoto} className="btn btn-primary">
                    <Camera size={16} /> Snap Picture
                  </button>
                </>
              ) : (
                <>
                  <button onClick={() => setCapturedBlob(null)} className="btn btn-secondary">
                    Retake
                  </button>
                  <button onClick={confirmCapturedPhoto} className="btn btn-success">
                    Confirm & Analyze
                  </button>
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
