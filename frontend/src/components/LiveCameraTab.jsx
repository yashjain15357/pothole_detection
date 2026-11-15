import React, { useState, useRef, useEffect } from 'react';
import { 
  Camera, 
  Play, 
  Square, 
  AlertTriangle, 
  AlertCircle,
  CheckCircle, 
  RefreshCw,
  Clock,
  MapPin,
  FileText,
  Navigation
} from 'lucide-react';
import { apiUrl, safeFetchJson } from '../apiConfig';

export default function LiveCameraTab({ onToast, onViewReport }) {
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState('');
  const [liveStats, setLiveStats] = useState({
    currentCount: 0,
    uniqueCount: 0,
    totalFrames: 0,
    runtimeSeconds: 0,
  });
  const [currentGps, setCurrentGps] = useState(null);
  const [detectedIncidents, setDetectedIncidents] = useState({});
  const [sessionReport, setSessionReport] = useState(null);

  const videoRef = useRef(null);
  const overlayCanvasRef = useRef(null);
  const captureCanvasRef = useRef(null);
  const streamRef = useRef(null);
  const detectIntervalRef = useRef(null);
  const timerIntervalRef = useRef(null);
  const startTimeRef = useRef(null);
  const isProcessingRef = useRef(false);
  const gpsWatchIdRef = useRef(null);
  const currentGpsRef = useRef(null);
  const detectedPotholeLocationsRef = useRef({});

  // Stop camera on unmount
  useEffect(() => {
    return () => {
      stopCameraSession();
    };
  }, []);

  // Track GPS location continuously when tab is active
  useEffect(() => {
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          const loc = { lat: pos.coords.latitude, lng: pos.coords.longitude };
          setCurrentGps(loc);
          currentGpsRef.current = loc;
        },
        () => console.log('Location permission pending')
      );

      const watchId = navigator.geolocation.watchPosition(
        (pos) => {
          const loc = { lat: pos.coords.latitude, lng: pos.coords.longitude };
          setCurrentGps(loc);
          currentGpsRef.current = loc;
        },
        (err) => console.log('GPS watch error:', err.message),
        { enableHighAccuracy: true, maximumAge: 5000, timeout: 10000 }
      );
      gpsWatchIdRef.current = watchId;
    }

    return () => {
      if (gpsWatchIdRef.current && navigator.geolocation) {
        navigator.geolocation.clearWatch(gpsWatchIdRef.current);
      }
    };
  }, []);

  const startCameraSession = async () => {
    setError('');
    setSessionReport(null);
    setLiveStats({ currentCount: 0, uniqueCount: 0, totalFrames: 0, runtimeSeconds: 0 });
    detectedPotholeLocationsRef.current = {};
    setDetectedIncidents({});
    isProcessingRef.current = false;

    try {
      // 1. Initialize camera tracking session on server
      const { response: initRes, data: initData } = await safeFetchJson(apiUrl('/start-camera-session'), {
        method: 'POST',
        credentials: 'include',
      });
      if (!initRes.ok) {
        throw new Error(initData.error || 'Failed to start camera session on server');
      }

      // 2. Access webcam directly
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { 
          width: { ideal: 1280, min: 640 }, 
          height: { ideal: 720, min: 480 }, 
          facingMode: 'environment' 
        },
        audio: false,
      });
      streamRef.current = stream;

      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        videoRef.current.onloadedmetadata = () => {
          videoRef.current.play().catch(e => console.error("Video play error:", e));
        };
      }

      setIsStreaming(true);
      startTimeRef.current = Date.now();

      // Start elapsed timer
      timerIntervalRef.current = setInterval(() => {
        const elapsed = Math.floor((Date.now() - startTimeRef.current) / 1000);
        setLiveStats((prev) => ({ ...prev, runtimeSeconds: elapsed }));
      }, 1000);

      // Start YOLO frame detection loop (every 450ms)
      detectIntervalRef.current = setInterval(captureAndDetectFrame, 450);
      onToast('Live camera started with real-time YOLO pothole inference!', 'success');
    } catch (err) {
      setError('Camera access error: ' + err.message);
      stopCameraSession();
    }
  };

  const captureAndDetectFrame = async () => {
    if (!videoRef.current || isProcessingRef.current || !streamRef.current) return;
    const video = videoRef.current;

    // Check if video is loaded and playing
    if (video.readyState < 2 || video.videoWidth === 0 || video.videoHeight === 0) {
      return;
    }

    isProcessingRef.current = true;

    try {
      if (!captureCanvasRef.current) {
        captureCanvasRef.current = document.createElement('canvas');
      }
      const captureCanvas = captureCanvasRef.current;
      
      // Inference resolution (416x320 for rapid CPU detection)
      const targetWidth = 416;
      const targetHeight = Math.round((video.videoHeight / video.videoWidth) * targetWidth);
      captureCanvas.width = targetWidth;
      captureCanvas.height = targetHeight;

      const ctx = captureCanvas.getContext('2d');
      ctx.drawImage(video, 0, 0, targetWidth, targetHeight);

      // Convert frame to base64 JPEG
      const base64Data = captureCanvas.toDataURL('image/jpeg', 0.75);

      const { response, data } = await safeFetchJson(apiUrl('/detect-frame'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ image: base64Data }),
      });

      if (response.ok && data.success) {
        const pCount = data.pothole_count ?? data.potholes_count ?? 0;
        const uCount = data.unique_count ?? data.unique_potholes_count ?? 0;

        setLiveStats((prev) => ({
          ...prev,
          currentCount: pCount,
          uniqueCount: uCount || prev.uniqueCount,
          totalFrames: prev.totalFrames + 1,
        }));

        // If potholes detected, record GPS location for this incident
        if (pCount > 0 && currentGpsRef.current) {
          const boxes = data.boxes || [];
          boxes.forEach((box) => {
            const pId = box.id || box.pothole_id || `Pothole_${Date.now()}`;
            if (!detectedPotholeLocationsRef.current[pId]) {
              detectedPotholeLocationsRef.current[pId] = {
                lat: currentGpsRef.current.lat,
                lng: currentGpsRef.current.lng,
                timestamp: new Date().toLocaleTimeString(),
              };
            }
          });
          setDetectedIncidents({ ...detectedPotholeLocationsRef.current });
        }

        // Render cyan bounding boxes on the overlay canvas
        renderBoundingBoxes(data.boxes || [], targetWidth, targetHeight);
      }
    } catch (err) {
      console.log('Frame inference error:', err.message);
    } finally {
      isProcessingRef.current = false;
    }
  };

  const renderBoundingBoxes = (boxes, modelWidth, modelHeight) => {
    if (!overlayCanvasRef.current || !videoRef.current) return;
    const canvas = overlayCanvasRef.current;
    const video = videoRef.current;
    const ctx = canvas.getContext('2d');

    const displayWidth = video.clientWidth;
    const displayHeight = video.clientHeight;

    if (canvas.width !== displayWidth || canvas.height !== displayHeight) {
      canvas.width = displayWidth;
      canvas.height = displayHeight;
    }

    // Clear previous bounding boxes
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    if (!boxes || boxes.length === 0) return;

    const scaleX = displayWidth / modelWidth;
    const scaleY = displayHeight / modelHeight;

    boxes.forEach((box) => {
      const pId = box.id ?? box.pothole_id ?? 1;
      const conf = box.confidence || '';
      const x1 = (box.x1 || 0) * scaleX;
      const y1 = (box.y1 || 0) * scaleY;
      const width = ((box.x2 || 0) - (box.x1 || 0)) * scaleX;
      const height = ((box.y2 || 0) - (box.y1 || 0)) * scaleY;

      // Cyan bounding box with high visibility
      ctx.strokeStyle = '#00ffff';
      ctx.lineWidth = 3;
      ctx.shadowColor = '#00ffff';
      ctx.shadowBlur = 8;
      ctx.strokeRect(x1, y1, width, height);
      ctx.shadowBlur = 0; // reset shadow

      // Label badge
      const label = `⚠️ Pothole #${pId} ${conf ? `(${conf})` : ''}`;
      ctx.font = 'bold 13px sans-serif';
      const textWidth = ctx.measureText(label).width;

      ctx.fillStyle = 'rgba(0, 255, 255, 0.9)';
      ctx.fillRect(x1, Math.max(0, y1 - 22), textWidth + 10, 22);

      ctx.fillStyle = '#000000';
      ctx.fillText(label, x1 + 5, Math.max(16, y1 - 6));
    });
  };

  const stopCameraSession = async () => {
    if (detectIntervalRef.current) clearInterval(detectIntervalRef.current);
    if (timerIntervalRef.current) clearInterval(timerIntervalRef.current);

    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }

    if (overlayCanvasRef.current) {
      const ctx = overlayCanvasRef.current.getContext('2d');
      ctx.clearRect(0, 0, overlayCanvasRef.current.width, overlayCanvasRef.current.height);
    }

    const elapsed = startTimeRef.current ? Math.floor((Date.now() - startTimeRef.current) / 1000) : 0;
    setIsStreaming(false);

    // Save final report to server with recorded locations
    if (liveStats.totalFrames > 0) {
      try {
        const payload = {
          runtime_seconds: elapsed,
          total_detections: liveStats.currentCount,
          unique_potholes: liveStats.uniqueCount,
          timestamp: new Date().toLocaleString(),
          latitude: currentGpsRef.current?.lat,
          longitude: currentGpsRef.current?.lng,
          pothole_locations: detectedPotholeLocationsRef.current,
        };

        const { response: res, data: reportData } = await safeFetchJson(apiUrl('/save-camera-report'), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body: JSON.stringify(payload),
        });
        if (res.ok && reportData.success) {
          setSessionReport({
            id: reportData.report_id,
            runtime: elapsed,
            uniqueCount: liveStats.uniqueCount,
            totalFrames: liveStats.totalFrames,
            locationsCount: Object.keys(detectedPotholeLocationsRef.current).length,
            gps: currentGpsRef.current,
          });
          onToast('Live inspection finished! Report saved with GPS coordinates.', 'success');
        }
      } catch (err) {
        console.error('Error saving camera report:', err);
      }
    }
  };

  const incidentCount = Object.keys(detectedIncidents).length;

  return (
    <div>
      <div style={{ marginBottom: '24px' }}>
        <h2 style={{ fontSize: '1.5rem', fontWeight: 800, color: '#0f172a' }}>Real-Time Live Camera Feed</h2>
        <p style={{ color: '#64748b', fontSize: '0.9rem' }}>
          Smooth live camera stream with real-time YOLO pothole detection & automated GPS road tagging
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

      {/* Control Bar & Live Stats */}
      <div className="card" style={{ marginBottom: '20px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '16px' }}>
          <div style={{ display: 'flex', gap: '20px', flexWrap: 'wrap', alignItems: 'center' }}>
            <div>
              <span style={{ fontSize: '0.75rem', color: '#64748b', textTransform: 'uppercase', fontWeight: 700 }}>
                Unique Potholes
              </span>
              <p style={{ fontSize: '1.6rem', fontWeight: 800, color: '#ef4444' }}>
                {liveStats.uniqueCount}
              </p>
            </div>

            <div>
              <span style={{ fontSize: '0.75rem', color: '#64748b', textTransform: 'uppercase', fontWeight: 700 }}>
                Current Frame
              </span>
              <p style={{ fontSize: '1.6rem', fontWeight: 800, color: '#4f46e5' }}>
                {liveStats.currentCount}
              </p>
            </div>

            <div>
              <span style={{ fontSize: '0.75rem', color: '#64748b', textTransform: 'uppercase', fontWeight: 700 }}>
                Duration
              </span>
              <p style={{ fontSize: '1.6rem', fontWeight: 800, color: '#0f172a' }}>
                {liveStats.runtimeSeconds}s
              </p>
            </div>

            {/* GPS Status Indicator */}
            <div style={{
              background: '#f1f5f9',
              padding: '8px 14px',
              borderRadius: '8px',
              border: '1px solid #e2e8f0',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
            }}>
              <Navigation size={16} color={currentGps ? '#10b981' : '#94a3b8'} />
              <div>
                <span style={{ fontSize: '0.7rem', color: '#64748b', fontWeight: 700, textTransform: 'uppercase' }}>
                  GPS Location:
                </span>
                <p style={{ fontSize: '0.85rem', fontWeight: 700, color: '#1e293b' }}>
                  {currentGps ? `${currentGps.lat.toFixed(5)}, ${currentGps.lng.toFixed(5)}` : 'Detecting GPS...'}
                </p>
              </div>
            </div>

            {incidentCount > 0 && (
              <span className="badge" style={{ background: '#fef2f2', color: '#b91c1c' }}>
                📍 {incidentCount} Pothole Location(s) Tagged
              </span>
            )}
          </div>

          <div>
            {!isStreaming ? (
              <button onClick={startCameraSession} className="btn btn-primary" style={{ padding: '12px 24px' }}>
                <Play size={18} /> Start Live Inspection
              </button>
            ) : (
              <button onClick={stopCameraSession} className="btn btn-danger" style={{ padding: '12px 24px' }}>
                <Square size={18} /> Stop & Save Report
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Video Viewport Container */}
      <div className="card" style={{ padding: '0', overflow: 'hidden', background: '#090d16' }}>
        <div style={{
          position: 'relative',
          minHeight: '440px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: '#090d16'
        }}>
          {/* Visible Video Player: Full framerate stream without black screen */}
          <video
            ref={videoRef}
            autoPlay
            playsInline
            muted
            style={{
              width: '100%',
              maxHeight: '540px',
              objectFit: 'contain',
              display: isStreaming ? 'block' : 'none',
              backgroundColor: '#000',
            }}
          />

          {/* Transparent Overlay Canvas for Cyan Bounding Boxes & Labels */}
          <canvas
            ref={overlayCanvasRef}
            style={{
              position: 'absolute',
              top: 0,
              left: 0,
              width: '100%',
              height: '100%',
              pointerEvents: 'none',
              display: isStreaming ? 'block' : 'none',
            }}
          />

          {/* Inactive Camera Placeholder */}
          {!isStreaming && !sessionReport && (
            <div style={{ textAlign: 'center', color: '#94a3b8', padding: '60px 20px' }}>
              <Camera size={56} style={{ margin: '0 auto 16px', opacity: 0.5 }} />
              <h3 style={{ color: '#e2e8f0', fontSize: '1.2rem', marginBottom: '8px' }}>Camera Inactive</h3>
              <p style={{ maxWidth: '440px', margin: '0 auto', fontSize: '0.85rem', lineHeight: '1.6' }}>
                Click "Start Live Inspection" to activate your camera. Live video will stream smoothly while YOLO annotates detected potholes with road GPS coordinates in real time.
              </p>
            </div>
          )}

          {/* Session Complete Report Card */}
          {sessionReport && !isStreaming && (
            <div style={{ textAlign: 'center', padding: '40px 20px', color: '#fff', maxWidth: '500px', margin: '0 auto' }}>
              <CheckCircle size={52} color="#10b981" style={{ margin: '0 auto 12px' }} />
              <h3 style={{ fontSize: '1.4rem', fontWeight: 800, marginBottom: '6px' }}>
                Live Inspection Complete!
              </h3>
              <p style={{ color: '#cbd5e1', fontSize: '0.9rem', marginBottom: '18px' }}>
                Detected <strong>{sessionReport.uniqueCount}</strong> unique potholes across <strong>{sessionReport.totalFrames}</strong> frames in {sessionReport.runtime}s.
              </p>

              {sessionReport.gps && (
                <div style={{
                  background: 'rgba(255, 255, 255, 0.1)',
                  borderRadius: '8px',
                  padding: '10px 14px',
                  marginBottom: '20px',
                  fontSize: '0.85rem'
                }}>
                  <p style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px', color: '#38bdf8' }}>
                    <MapPin size={16} />
                    <span>Location Tagged: {sessionReport.gps.lat.toFixed(6)}, {sessionReport.gps.lng.toFixed(6)}</span>
                  </p>
                  <p style={{ fontSize: '0.78rem', color: '#94a3b8', marginTop: '4px' }}>
                    {sessionReport.locationsCount} pothole coordinates stored in report #{sessionReport.id}
                  </p>
                </div>
              )}

              <div style={{ display: 'flex', justifyContent: 'center', gap: '12px' }}>
                <button onClick={startCameraSession} className="btn btn-primary">
                  <RefreshCw size={16} /> New Session
                </button>
                {sessionReport.id && onViewReport && (
                  <button
                    onClick={() => onViewReport(sessionReport.id)}
                    className="btn btn-secondary"
                    style={{ background: '#334155', color: '#fff', border: 'none' }}
                  >
                    <FileText size={16} /> View Saved Report
                  </button>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
