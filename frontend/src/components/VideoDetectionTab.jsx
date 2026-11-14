import React, { useState } from 'react';
import { 
  Video, 
  Upload, 
  CheckCircle, 
  AlertCircle, 
  MapPin, 
  Save, 
  RefreshCw,
  Film,
  Activity
} from 'lucide-react';
import LeafletMapPicker from './LeafletMapPicker';

export default function VideoDetectionTab({ onToast }) {
  const [selectedFile, setSelectedFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState(null);

  // Map location state
  const [latitude, setLatitude] = useState(23.5183);
  const [longitude, setLongitude] = useState(77.8128);
  const [savingLocation, setSavingLocation] = useState(false);
  const [locationSaved, setLocationSaved] = useState(false);

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      setSelectedFile(e.target.files[0]);
      setError('');
    }
  };

  const processVideoFile = async () => {
    if (!selectedFile) return;

    setLoading(true);
    setError('');
    setResult(null);
    setLocationSaved(false);

    const formData = new FormData();
    formData.append('file', selectedFile);

    try {
      const response = await fetch('/upload-video', {
        method: 'POST',
        credentials: 'include',
        body: formData,
      });

      const data = await response.json();

      if (response.ok && data.success !== false) {
        setResult(data);
        onToast('Video processed successfully with centroid tracking!', 'success');
      } else {
        setError(data.error || 'Failed to process video');
      }
    } catch (err) {
      setError('Error communicating with video processing service: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleSaveLocation = async () => {
    setSavingLocation(true);
    try {
      const res = await fetch('/save-video-location-with-report', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          report: result?.report || {},
          report_id: result?.report?.id,
          location: {
            lat: Number(latitude),
            lng: Number(longitude)
          },
          latitude: Number(latitude),
          longitude: Number(longitude),
        }),
      });

      const data = await res.json();
      if (res.ok && data.success) {
        setLocationSaved(true);
        onToast('Video report geotagged successfully!', 'success');
      } else {
        onToast(data.error || 'Failed to save location', 'error');
      }
    } catch (err) {
      onToast('Error saving location: ' + err.message, 'error');
    } finally {
      setSavingLocation(false);
    }
  };

  const rep = result?.report || {};

  return (
    <div>
      <div style={{ marginBottom: '24px' }}>
        <h2 style={{ fontSize: '1.5rem', fontWeight: 800, color: '#0f172a' }}>Video Pothole Detection</h2>
        <p style={{ color: '#64748b', fontSize: '0.9rem' }}>
          Analyze road inspection drive footage with automated multi-frame tracking
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

      {/* Upload Dropzone */}
      {!result && (
        <div className="card" style={{ maxWidth: '750px', margin: '0 auto 24px' }}>
          <div
            className="dropzone"
            onClick={() => document.getElementById('video-file-input').click()}
          >
            <input
              id="video-file-input"
              type="file"
              accept="video/*"
              onChange={handleFileChange}
              style={{ display: 'none' }}
            />
            <Video className="dropzone-icon" style={{ color: '#f59e0b' }} />
            <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: '#1e293b', marginBottom: '6px' }}>
              {selectedFile ? selectedFile.name : 'Upload Road Inspection Video'}
            </h3>
            <p style={{ fontSize: '0.85rem', color: '#64748b' }}>
              Accepts MP4, AVI, MOV, MKV, FLV up to 500MB
            </p>

            {selectedFile && (
              <div style={{ marginTop: '20px' }}>
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    processVideoFile();
                  }}
                  disabled={loading}
                  className="btn btn-primary"
                  style={{ background: '#f59e0b' }}
                >
                  {loading ? (
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <div className="spinner" />
                      <span>Analyzing Video Frames...</span>
                    </div>
                  ) : (
                    <><Film size={18} /> Start Video Inference</>
                  )}
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Detection Results */}
      {result && (
        <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: '24px' }}>
          <div className="card">
            <div className="card-header">
              <h3 className="card-title">
                <CheckCircle size={20} color="#10b981" />
                Video Analysis Results
              </h3>
              <button
                onClick={() => {
                  setResult(null);
                  setSelectedFile(null);
                }}
                className="btn btn-secondary"
                style={{ padding: '6px 12px', fontSize: '0.8rem' }}
              >
                <RefreshCw size={14} /> Scan Another Video
              </button>
            </div>

            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(2, 1fr)',
              gap: '16px',
              marginBottom: '20px'
            }}>
              <div style={{ background: '#f8fafc', padding: '16px', borderRadius: '10px', border: '1px solid #e2e8f0' }}>
                <span style={{ fontSize: '0.75rem', color: '#64748b', textTransform: 'uppercase', fontWeight: 700 }}>
                  Unique Potholes
                </span>
                <p style={{ fontSize: '1.8rem', fontWeight: 800, color: '#0f172a', marginTop: '4px' }}>
                  {rep.unique_potholes ?? rep.pothole_count ?? 0}
                </p>
                <span style={{ fontSize: '0.75rem', color: '#10b981' }}>Centroid Tracking De-duplicated</span>
              </div>

              <div style={{ background: '#f8fafc', padding: '16px', borderRadius: '10px', border: '1px solid #e2e8f0' }}>
                <span style={{ fontSize: '0.75rem', color: '#64748b', textTransform: 'uppercase', fontWeight: 700 }}>
                  Total Detections Across Frames
                </span>
                <p style={{ fontSize: '1.8rem', fontWeight: 800, color: '#4f46e5', marginTop: '4px' }}>
                  {rep.total_potholes_detected || 0}
                </p>
                <span style={{ fontSize: '0.75rem', color: '#64748b' }}>Cumulative count</span>
              </div>

              <div style={{ background: '#f8fafc', padding: '16px', borderRadius: '10px', border: '1px solid #e2e8f0' }}>
                <span style={{ fontSize: '0.75rem', color: '#64748b', textTransform: 'uppercase', fontWeight: 700 }}>
                  Total Frames Analyzed
                </span>
                <p style={{ fontSize: '1.8rem', fontWeight: 800, color: '#0f172a', marginTop: '4px' }}>
                  {rep.total_frames || 0}
                </p>
                <span style={{ fontSize: '0.75rem', color: '#64748b' }}>{rep.fps || 30} FPS</span>
              </div>

              <div style={{ background: '#f8fafc', padding: '16px', borderRadius: '10px', border: '1px solid #e2e8f0' }}>
                <span style={{ fontSize: '0.75rem', color: '#64748b', textTransform: 'uppercase', fontWeight: 700 }}>
                  Frames With Potholes
                </span>
                <p style={{ fontSize: '1.8rem', fontWeight: 800, color: '#ef4444', marginTop: '4px' }}>
                  {rep.frames_with_detections || 0}
                </p>
                <span style={{ fontSize: '0.75rem', color: '#64748b' }}>Impacted footage slices</span>
              </div>
            </div>

            <div style={{ background: '#f1f5f9', padding: '14px', borderRadius: '8px', fontSize: '0.85rem' }}>
              <p><strong>Processed File:</strong> {rep.filename || selectedFile?.name}</p>
              <p><strong>Timestamp:</strong> {rep.timestamp}</p>
            </div>
          </div>

          {/* Geotagging Map */}
          <div className="card">
            <div className="card-header">
              <h3 className="card-title">
                <MapPin size={20} color="#f59e0b" />
                Tag Video Inspection Road Location
              </h3>
              {locationSaved && (
                <span className="badge" style={{ background: '#ecfdf5', color: '#059669' }}>
                  ✓ Location Saved
                </span>
              )}
            </div>

            <LeafletMapPicker
              latitude={latitude}
              longitude={longitude}
              onLocationChange={(lat, lng) => {
                setLatitude(lat);
                setLongitude(lng);
                setLocationSaved(false);
              }}
              height="300px"
            />

            <div style={{ marginTop: '18px', textAlign: 'right' }}>
              <button
                type="button"
                onClick={handleSaveLocation}
                disabled={savingLocation || locationSaved}
                className="btn btn-primary"
                style={{ width: '100%' }}
              >
                {savingLocation ? (
                  <div className="spinner" />
                ) : (
                  <><Save size={16} /> {locationSaved ? 'Geotag Associated' : 'Save Geotag to Video Report'}</>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
