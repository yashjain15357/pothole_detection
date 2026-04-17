// Tab Navigation
const navBtns = document.querySelectorAll('.nav-btn');
const tabContents = document.querySelectorAll('.tab-content');

navBtns.forEach(btn => {
    btn.addEventListener('click', () => {
        const tabName = btn.dataset.tab;
        
        // Remove active class from all buttons and tabs
        navBtns.forEach(b => b.classList.remove('active'));
        tabContents.forEach(tc => tc.classList.remove('active'));
        
        // Add active class to clicked button and corresponding tab
        btn.classList.add('active');
        document.getElementById(`${tabName}-tab`).classList.add('active');
    });
});

// ============ IMAGE UPLOAD HANDLING ============

const loadImageBtn = document.getElementById('load-image-btn');
const imageInput = document.getElementById('image-input');
const imageLoading = document.getElementById('image-loading');
const imageResults = document.getElementById('image-results');
const imageError = document.getElementById('image-error');

loadImageBtn.addEventListener('click', () => {
    imageInput.click();
});

imageInput.addEventListener('change', uploadImage);

let deviceUploadedFile = null;
let deviceUploadedData = null;

function uploadImage() {
    if (!imageInput.files || imageInput.files.length === 0) {
        showImageError('Please select an image first');
        return;
    }

    const formData = new FormData();
    formData.append('file', imageInput.files[0]);
    deviceUploadedFile = imageInput.files[0];

    imageLoading.classList.remove('hidden');
    imageResults.classList.add('hidden');
    imageError.classList.add('hidden');

    fetch('/upload-image', {
        method: 'POST',
        body: formData
    })
    .then(response => {
        if (!response.ok) throw new Error('Upload failed');
        return response.json();
    })
    .then(data => {
        imageLoading.classList.add('hidden');
        
        if (data.success === false) {
            showImageError(data.error || 'Unknown error occurred');
            return;
        }

        deviceUploadedData = data;
        // Show location selection instead of results
        showLocationSelection();
    })
    .catch(error => {
        imageLoading.classList.add('hidden');
        showImageError('Error uploading image: ' + error.message);
    });
}

function displayImageResults(data) {
    const report = data.report;
    
    // Display image
    const detectedImage = document.getElementById('detected-image');
    detectedImage.src = 'data:image/jpeg;base64,' + data.image_base64;

    // Build report text
    let reportText = `POTHOLE DETECTION REPORT
${'='.repeat(60)}

Timestamp: ${report.timestamp}
Image: ${report.filename}
Potholes Detected: ${report.pothole_count}`;

    // Add location if available
    if (report.location) {
        reportText += `
Latitude: ${report.location.latitude.toFixed(6)}
Longitude: ${report.location.longitude.toFixed(6)}`;
    }

    reportText += `

${'='.repeat(60)}`;

    if (report.detections.length > 0) {
        reportText += '\n\nDetection Details:\n' + '-'.repeat(60);
        report.detections.forEach(det => {
            reportText += `\nPothole ${det.pothole_id}: Confidence = ${det.confidence}, Width = ${det.width_px}px, Height = ${det.height_px}px`;
        });
    } else {
        reportText += '\n\nNo potholes detected';
    }

    document.getElementById('image-report').textContent = reportText;
    imageResults.classList.remove('hidden');
}

function showImageError(message) {
    imageError.textContent = message;
    imageError.classList.remove('hidden');
}

// ============ CAMERA CAPTURE HANDLING ============

const captureImageBtn = document.getElementById('capture-image-btn');
const imageCameraModal = document.getElementById('image-camera-modal');
const imageCaptureVideo = document.getElementById('image-capture-video');
const imageCaptureBtnElement = document.getElementById('image-capture-btn');
const cancelCaptureBtn = document.getElementById('cancel-capture-btn');
const imageCaptureCanvas = document.getElementById('image-capture-canvas');
const imageCapturePreview = document.getElementById('image-capture-preview');
const imageCaptureResult = document.getElementById('image-capture-result');
const confirmCaptureBtn = document.getElementById('confirm-capture-btn');
const retakeBtn = document.getElementById('retake-btn');
const closeImageCameraBtn = document.getElementById('close-image-camera');

let imageCameraStream = null;
let capturedCameraLocation = null;

captureImageBtn.addEventListener('click', () => {
    imageCameraModal.classList.remove('hidden');
    startImageCamera();
});

closeImageCameraBtn.addEventListener('click', () => {
    stopImageCamera();
    imageCameraModal.classList.add('hidden');
});

cancelCaptureBtn.addEventListener('click', () => {
    stopImageCamera();
    imageCameraModal.classList.add('hidden');
});

imageCameraModal.addEventListener('click', (e) => {
    if (e.target === imageCameraModal) {
        stopImageCamera();
        imageCameraModal.classList.add('hidden');
    }
});

async function startImageCamera() {
    try {
        imageCameraStream = await navigator.mediaDevices.getUserMedia({
            video: { facingMode: 'environment' }
        });
        imageCaptureVideo.srcObject = imageCameraStream;
        imageCaptureVideo.style.display = 'block';
        imageCapturePreview.classList.add('hidden');
    } catch (error) {
        showImageError('Error accessing camera: ' + error.message);
        imageCameraModal.classList.add('hidden');
    }
}

function stopImageCamera() {
    if (imageCameraStream) {
        imageCameraStream.getTracks().forEach(track => track.stop());
        imageCameraStream = null;
    }
}

imageCaptureBtnElement.addEventListener('click', () => {
    const context = imageCaptureCanvas.getContext('2d');
    imageCaptureCanvas.width = imageCaptureVideo.videoWidth;
    imageCaptureCanvas.height = imageCaptureVideo.videoHeight;
    context.drawImage(imageCaptureVideo, 0, 0);
    
    // Get current location when capturing photo
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            (position) => {
                capturedCameraLocation = {
                    lat: position.coords.latitude,
                    lng: position.coords.longitude
                };
                displayCaptureWithLocation();
            },
            (error) => {
                console.log('Could not get location:', error.message);
                capturedCameraLocation = null;
                displayCaptureWithLocation();
            }
        );
    } else {
        capturedCameraLocation = null;
        displayCaptureWithLocation();
    }
});

function displayCaptureWithLocation() {
    imageCaptureCanvas.toBlob((blob) => {
        const url = URL.createObjectURL(blob);
        imageCaptureResult.src = url;
        imageCaptureVideo.style.display = 'none';
        imageCapturePreview.classList.remove('hidden');
        imageCapturePreview.capturedBlob = blob;
        
        // Display location info if available
        const captureLocationInfo = document.getElementById('camera-capture-location-info');
        if (capturedCameraLocation) {
            document.getElementById('camera-capture-lat').textContent = capturedCameraLocation.lat.toFixed(6);
            document.getElementById('camera-capture-lng').textContent = capturedCameraLocation.lng.toFixed(6);
            captureLocationInfo.classList.remove('hidden');
        } else {
            captureLocationInfo.classList.add('hidden');
        }
    }, 'image/jpeg', 0.95);
}

retakeBtn.addEventListener('click', () => {
    imageCaptureVideo.style.display = 'block';
    imageCapturePreview.classList.add('hidden');
});

confirmCaptureBtn.addEventListener('click', () => {
    const blob = imageCapturePreview.capturedBlob;
    const formData = new FormData();
    formData.append('file', blob, 'captured_image.jpg');
    
    // Add location if available
    if (capturedCameraLocation) {
        formData.append('latitude', capturedCameraLocation.lat);
        formData.append('longitude', capturedCameraLocation.lng);
    }
    
    stopImageCamera();
    imageCameraModal.classList.add('hidden');
    
    imageLoading.classList.remove('hidden');
    imageResults.classList.add('hidden');
    imageError.classList.add('hidden');
    
    fetch('/upload-image', {
        method: 'POST',
        body: formData
    })
    .then(response => {
        if (!response.ok) throw new Error('Upload failed');
        return response.json();
    })
    .then(data => {
        imageLoading.classList.add('hidden');
        
        if (data.success === false) {
            showImageError(data.error || 'Unknown error occurred');
            return;
        }
        
        displayImageResults(data);
    })
    .catch(error => {
        imageLoading.classList.add('hidden');
        showImageError('Error processing image: ' + error.message);
    });
});

// ============ LOCATION SELECTION FOR DEVICE UPLOADED IMAGE ============

const locationSelectionContainer = document.getElementById('location-selection-container');
const confirmLocationBtn = document.getElementById('confirm-location-btn');
const cancelLocationBtn = document.getElementById('cancel-location-btn');
const selectedLatSpan = document.getElementById('selected-lat');
const selectedLngSpan = document.getElementById('selected-lng');
const locationInfo = document.getElementById('location-info');

let mapInstance = null;
let selectedLocation = null;
let locationMarker = null;

function showLocationSelection() {
    locationSelectionContainer.classList.remove('hidden');
    imageResults.classList.add('hidden');
    
    // Initialize map on first use
    if (!mapInstance) {
        setTimeout(() => {
            initializeLocationMap();
        }, 100);
    }
}

function initializeLocationMap() {
    const mapContainer = document.getElementById('image-location-map');
    
    if (mapInstance) {
        mapInstance.remove();
    }
    
    // Get user's current location or default to center
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            (position) => {
                const lat = position.coords.latitude;
                const lng = position.coords.longitude;
                createMap(lat, lng);
            },
            () => {
                // Default to center location if geolocation fails
                createMap(20, 78);
            }
        );
    } else {
        createMap(20, 78);
    }
}

function createMap(lat, lng) {
    const mapContainer = document.getElementById('image-location-map');
    mapInstance = L.map(mapContainer).setView([lat, lng], 13);
    
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors',
        maxZoom: 19
    }).addTo(mapInstance);
    
    // Handle map clicks for location selection
    mapInstance.on('click', (e) => {
        const lat = e.latlng.lat;
        const lng = e.latlng.lng;
        selectLocation(lat, lng);
    });
}

function selectLocation(lat, lng) {
    selectedLocation = { lat, lng };
    
    // Remove previous marker
    if (locationMarker) {
        mapInstance.removeLayer(locationMarker);
    }
    
    // Add new marker
    locationMarker = L.marker([lat, lng])
        .bindPopup(`<b>Selected Location</b><br>Lat: ${lat.toFixed(4)}<br>Lng: ${lng.toFixed(4)}`)
        .addTo(mapInstance)
        .openPopup();
    
    // Update location display
    selectedLatSpan.textContent = lat.toFixed(6);
    selectedLngSpan.textContent = lng.toFixed(6);
    locationInfo.classList.remove('hidden');
    
    // Enable confirm button
    confirmLocationBtn.disabled = false;
}

confirmLocationBtn.addEventListener('click', () => {
    if (!selectedLocation) {
        showImageError('Please select a location on the map');
        return;
    }
    
    // Add location to the data and display results
    if (deviceUploadedData) {
        deviceUploadedData.report.location = {
            latitude: selectedLocation.lat,
            longitude: selectedLocation.lng
        };
    }
    
    locationSelectionContainer.classList.add('hidden');
    displayImageResults(deviceUploadedData);
    
    // Save location with report
    saveLocationWithReport();
});

cancelLocationBtn.addEventListener('click', () => {
    locationSelectionContainer.classList.add('hidden');
    deviceUploadedData = null;
    deviceUploadedFile = null;
    selectedLocation = null;
    locationMarker = null;
    locationInfo.classList.add('hidden');
    confirmLocationBtn.disabled = true;
});

function saveLocationWithReport() {
    if (!selectedLocation || !deviceUploadedData) return;
    
    const reportData = {
        report: deviceUploadedData.report,
        location: selectedLocation
    };
    
    // Send to backend to save with report
    fetch('/save-location-with-report', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(reportData)
    })
    .catch(error => console.log('Location saved locally:', selectedLocation));
}

// ============ VIDEO UPLOAD HANDLING ============

const loadVideoBtn = document.getElementById('load-video-btn');
const videoInput = document.getElementById('video-input');
const videoLoading = document.getElementById('video-loading');
const videoResults = document.getElementById('video-results');
const videoError = document.getElementById('video-error');

let deviceUploadedVideoFile = null;
let deviceUploadedVideoData = null;
let videoMapInstance = null;
let videoSelectedLocation = null;
let videoLocationMarker = null;

const videoLocationSelectionContainer = document.getElementById('video-location-selection-container');
const videoConfirmLocationBtn = document.getElementById('video-confirm-location-btn');
const videoCancelLocationBtn = document.getElementById('video-cancel-location-btn');
const videoSelectedLatSpan = document.getElementById('video-selected-lat');
const videoSelectedLngSpan = document.getElementById('video-selected-lng');
const videoLocationInfo = document.getElementById('video-location-info');

loadVideoBtn.addEventListener('click', () => {
    videoInput.click();
});

videoInput.addEventListener('change', uploadVideo);

function uploadVideo() {
    if (!videoInput.files || videoInput.files.length === 0) {
        showVideoError('Please select a video first');
        return;
    }

    const formData = new FormData();
    formData.append('file', videoInput.files[0]);
    deviceUploadedVideoFile = videoInput.files[0];

    videoLoading.classList.remove('hidden');
    videoResults.classList.add('hidden');
    videoError.classList.add('hidden');

    fetch('/upload-video', {
        method: 'POST',
        body: formData
    })
    .then(response => {
        if (!response.ok) throw new Error('Processing failed');
        return response.json();
    })
    .then(data => {
        videoLoading.classList.add('hidden');
        
        if (data.success === false) {
            showVideoError(data.error || 'Unknown error occurred');
            return;
        }

        deviceUploadedVideoData = data;
        // Show location selection instead of results
        showVideoLocationSelection();
    })
    .catch(error => {
        videoLoading.classList.add('hidden');
        showVideoError('Error processing video: ' + error.message);
    });
}

function showVideoLocationSelection() {
    videoLocationSelectionContainer.classList.remove('hidden');
    videoResults.classList.add('hidden');
    
    // Initialize map on first use
    if (!videoMapInstance) {
        setTimeout(() => {
            initializeVideoLocationMap();
        }, 100);
    }
}

function initializeVideoLocationMap() {
    const mapContainer = document.getElementById('video-location-map');
    
    if (videoMapInstance) {
        videoMapInstance.remove();
    }
    
    // Get user's current location or default to center
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            (position) => {
                const lat = position.coords.latitude;
                const lng = position.coords.longitude;
                createVideoMap(lat, lng);
            },
            () => {
                // Default to center location if geolocation fails
                createVideoMap(20, 78);
            }
        );
    } else {
        createVideoMap(20, 78);
    }
}

function createVideoMap(lat, lng) {
    const mapContainer = document.getElementById('video-location-map');
    videoMapInstance = L.map(mapContainer).setView([lat, lng], 13);
    
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors',
        maxZoom: 19
    }).addTo(videoMapInstance);
    
    // Handle map clicks for location selection
    videoMapInstance.on('click', (e) => {
        const lat = e.latlng.lat;
        const lng = e.latlng.lng;
        selectVideoLocation(lat, lng);
    });
}

function selectVideoLocation(lat, lng) {
    videoSelectedLocation = { lat, lng };
    
    // Remove previous marker
    if (videoLocationMarker) {
        videoMapInstance.removeLayer(videoLocationMarker);
    }
    
    // Add new marker
    videoLocationMarker = L.marker([lat, lng])
        .bindPopup(`<b>Selected Location</b><br>Lat: ${lat.toFixed(4)}<br>Lng: ${lng.toFixed(4)}`)
        .addTo(videoMapInstance)
        .openPopup();
    
    // Update location display
    videoSelectedLatSpan.textContent = lat.toFixed(6);
    videoSelectedLngSpan.textContent = lng.toFixed(6);
    videoLocationInfo.classList.remove('hidden');
    
    // Enable confirm button
    videoConfirmLocationBtn.disabled = false;
}

videoConfirmLocationBtn.addEventListener('click', () => {
    if (!videoSelectedLocation) {
        showVideoError('Please select a location on the map');
        return;
    }
    
    // Add location to the data and display results
    if (deviceUploadedVideoData) {
        deviceUploadedVideoData.report.location = {
            latitude: videoSelectedLocation.lat,
            longitude: videoSelectedLocation.lng
        };
    }
    
    videoLocationSelectionContainer.classList.add('hidden');
    displayVideoResults(deviceUploadedVideoData);
    
    // Save location with report
    saveVideoLocationWithReport();
});

videoCancelLocationBtn.addEventListener('click', () => {
    videoLocationSelectionContainer.classList.add('hidden');
    deviceUploadedVideoData = null;
    deviceUploadedVideoFile = null;
    videoSelectedLocation = null;
    videoLocationMarker = null;
    videoLocationInfo.classList.add('hidden');
    videoConfirmLocationBtn.disabled = true;
});

function saveVideoLocationWithReport() {
    if (!videoSelectedLocation || !deviceUploadedVideoData) return;
    
    const reportData = {
        report: deviceUploadedVideoData.report,
        location: videoSelectedLocation
    };
    
    // Send to backend to save with report
    fetch('/save-video-location-with-report', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(reportData)
    })
    .catch(error => console.log('Location saved locally:', videoSelectedLocation));
}

function displayVideoResults(data) {
    const report = data.report;
    
    // Build summary stats HTML
    let summaryHtml = `
    <div class="video-summary">
        <div class="summary-grid">
            <div class="summary-card">
                <div class="summary-label">Timestamp</div>
                <div class="summary-value-text">${report.timestamp}</div>
            </div>
            <div class="summary-card">
                <div class="summary-label">Total Frames</div>
                <div class="summary-value">${report.total_frames}</div>
            </div>
            <div class="summary-card">
                <div class="summary-label">Frames with Potholes</div>
                <div class="summary-value">${report.frames_with_detections}</div>
            </div>
            <div class="summary-card">
                <div class="summary-label">Total Detected</div>
                <div class="summary-value">${report.total_potholes_detected}</div>
            </div>
            <div class="summary-card highlight">
                <div class="summary-label">Unique Potholes</div>
                <div class="summary-value">${report.unique_potholes}</div>
            </div>
            <div class="summary-card">
                <div class="summary-label">FPS</div>
                <div class="summary-value">${report.fps}</div>
            </div>`;

    // Add location if available
    if (report.location) {
        summaryHtml += `
            <div class="summary-card">
                <div class="summary-label">📍 Latitude</div>
                <div class="summary-value-text">${report.location.latitude.toFixed(6)}</div>
            </div>
            <div class="summary-card">
                <div class="summary-label">📍 Longitude</div>
                <div class="summary-value-text">${report.location.longitude.toFixed(6)}</div>
            </div>`;
    }

    summaryHtml += `
        </div>
    </div>`;
    
    document.getElementById('video-report').innerHTML = summaryHtml;
    videoResults.classList.remove('hidden');
}

function showVideoError(message) {
    videoError.textContent = message;
    videoError.classList.remove('hidden');
}

// ============ REPORTS HANDLING ============

const reportsLoading = document.getElementById('reports-loading');
const reportsContainer = document.getElementById('reports-container');
const reportsError = document.getElementById('reports-error');

const imageReportsList = document.getElementById('image-reports-list');
const videoReportsList = document.getElementById('video-reports-list');
const cameraReportsList = document.getElementById('camera-reports-list');

let autoRefreshInterval = null;

function loadReports() {
    reportsLoading.classList.remove('hidden');
    reportsContainer.classList.add('hidden');
    reportsError.classList.add('hidden');

    fetch('/reports')
    .then(response => {
        if (!response.ok) throw new Error('Failed to load reports');
        return response.json();
    })
    .then(data => {
        reportsLoading.classList.add('hidden');
        displayReports(data);
    })
    .catch(error => {
        reportsLoading.classList.add('hidden');
        reportsError.textContent = 'Error loading reports: ' + error.message;
        reportsError.classList.remove('hidden');
    });
}

function displayReports(data) {
    // Display image reports
    if (data.image_reports.length > 0) {
        imageReportsList.innerHTML = data.image_reports.map(report => 
            `<div class="report-item">
                <div style="flex: 1; cursor: pointer;" onclick="viewReportById(${report.id})">
                    📄 ${report.name}
                    <small>${new Date(report.created * 1000).toLocaleString()}</small>
                </div>
                <button class="btn btn-small" onclick="downloadReport('${report.path}', '${report.name}')" style="margin-left: auto;">⬇️ Download</button>
            </div>`
        ).join('');
    } else {
        imageReportsList.innerHTML = '<div class="empty-report">No image reports yet</div>';
    }

    // Display video reports
    if (data.video_reports.length > 0) {
        videoReportsList.innerHTML = data.video_reports.map(report => 
            `<div class="report-item">
                <div style="flex: 1; cursor: pointer;" onclick="viewReportById(${report.id})">
                    📄 ${report.name}
                    <small>${new Date(report.created * 1000).toLocaleString()}</small>
                </div>
                <button class="btn btn-small" onclick="downloadReport('${report.path}', '${report.name}')" style="margin-left: auto;">⬇️ Download</button>
            </div>`
        ).join('');
    } else {
        videoReportsList.innerHTML = '<div class="empty-report">No video reports yet</div>';
    }

    // Display camera reports
    if (data.camera_reports.length > 0) {
        cameraReportsList.innerHTML = data.camera_reports.map(report => 
            `<div class="report-item">
                <div style="flex: 1; cursor: pointer;" onclick="viewReportById(${report.id})">
                    📄 ${report.name}
                    <small>${new Date(report.created * 1000).toLocaleString()}</small>
                </div>
                <button class="btn btn-small" onclick="downloadReport('${report.path}', '${report.name}')" style="margin-left: auto;">⬇️ Download</button>
            </div>`
        ).join('');
    } else {
        cameraReportsList.innerHTML = '<div class="empty-report">No camera reports yet</div>';
    }

    reportsContainer.classList.remove('hidden');
}

// ============ MODAL HANDLING ============

const modal = document.getElementById('report-modal');
const closeBtn = document.querySelector('.close');
const modalReportContent = document.getElementById('modal-report-content');

closeBtn.addEventListener('click', () => {
    modal.classList.add('hidden');
});

window.addEventListener('click', (e) => {
    if (e.target === modal) {
        modal.classList.add('hidden');
    }
});

function viewReportById(reportId) {
    fetch(`/report-by-id/${reportId}`)
    .then(response => {
        if (!response.ok) {
            return response.json().then(data => {
                throw new Error(data.error || 'Failed to load report');
            });
        }
        return response.json();
    })
    .then(data => {
        modalReportContent.textContent = data.content;
        modal.classList.remove('hidden');
    })
    .catch(error => {
        alert('Error loading report: ' + error.message);
    });
}

function viewReport(reportPath) {
    const reportPath2 = reportPath.replace(/\\/g, '/');
    const encodedPath = encodeURIComponent(reportPath2);
    
    fetch(`/report/${encodedPath}`)
    .then(response => {
        if (!response.ok) {
            return response.json().then(data => {
                throw new Error(data.error || 'Failed to load report');
            });
        }
        return response.json();
    })
    .then(data => {
        modalReportContent.textContent = data.content;
        modal.classList.remove('hidden');
    })
    .catch(error => {
        alert('Error loading report: ' + error.message);
    });
}

function downloadReport(reportPath, reportName) {
    const reportPath2 = reportPath.replace(/\\/g, '/');
    
    // Create a temporary link and trigger download
    const link = document.createElement('a');
    link.href = `/download-report/${reportPath2}`;
    link.download = reportName;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

// Reports initialization
document.addEventListener('DOMContentLoaded', () => {
    // Load initial reports once
    loadReports();
});

// ============ CAMERA DETECTION HANDLING ============

const startCameraBtn = document.getElementById('start-camera-btn');
const stopCameraBtn = document.getElementById('stop-camera-btn');
const cameraVideo = document.getElementById('camera-video');
const cameraCanvas = document.getElementById('camera-canvas');
const cameraContainer = document.getElementById('camera-container');
const cameraLoading = document.getElementById('camera-loading');
const cameraError = document.getElementById('camera-error');
const detectionCountSpan = document.getElementById('detection-count');
const runtimeSpan = document.getElementById('runtime');
const uniqueIdsSpan = document.getElementById('unique-ids');

let cameraStream = null;
let isProcessing = false;
let startTime = null;
let totalDetections = 0;
let uniquePotholeIds = new Set();
let runtimeIntervalId = null;
let processingIntervalId = null;
let detectionAbortController = null;  // To cancel in-flight requests

// Pothole location tracking
let cameraLocationMap = null;
let detectedPotholeLocations = {};  // Store pothole ID -> { lat, lng, timestamp }
let potholeLocationMarkers = {};  // Store marker references

startCameraBtn.addEventListener('click', startCamera);
stopCameraBtn.addEventListener('click', stopCamera);

async function startCamera() {
    cameraLoading.classList.remove('hidden');
    cameraError.classList.add('hidden');
    
    try {
        // Initialize camera session on server
        const sessionResponse = await fetch('/start-camera-session', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        if (!sessionResponse.ok) {
            throw new Error('Failed to initialize camera session');
        }
        
        cameraStream = await navigator.mediaDevices.getUserMedia({
            video: { facingMode: 'environment' }
        });
        
        cameraVideo.srcObject = cameraStream;
        
        // Wait for video to be ready
        await new Promise((resolve) => {
            cameraVideo.onloadedmetadata = () => {
                console.log(`✓ Video loaded: ${cameraVideo.videoWidth}x${cameraVideo.videoHeight}`);
                resolve();
            };
        });
        
        cameraContainer.classList.remove('hidden');
        startCameraBtn.classList.add('hidden');
        stopCameraBtn.classList.remove('hidden');
        
        cameraLoading.classList.add('hidden');
        startTime = Date.now();
        totalDetections = 0;
        uniquePotholeIds.clear();
        detectedPotholeLocations = {};
        potholeLocationMarkers = {};
        isProcessing = true;
        detectionAbortController = new AbortController();  // Create new abort controller
        
        // Initialize location map
        initializeCameraLocationMap();
        
        console.log('✓ Camera session initialized');
        
        // Start processing frames
        processCamera();
        updateRuntime();
    } catch (error) {
        cameraLoading.classList.add('hidden');
        showCameraError('Camera access denied or not available: ' + error.message);
    }
}

function initializeCameraLocationMap() {
    const mapContainer = document.getElementById('camera-location-map');
    
    if (cameraLocationMap) {
        cameraLocationMap.remove();
    }
    
    // Get user's current location or default to center
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            (position) => {
                const lat = position.coords.latitude;
                const lng = position.coords.longitude;
                createCameraMap(lat, lng);
            },
            () => {
                // Default to center location if geolocation fails
                createCameraMap(20, 78);
            }
        );
    } else {
        createCameraMap(20, 78);
    }
}

function createCameraMap(lat, lng) {
    const mapContainer = document.getElementById('camera-location-map');
    cameraLocationMap = L.map(mapContainer).setView([lat, lng], 13);
    
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors',
        maxZoom: 19
    }).addTo(cameraLocationMap);
}

async function stopCamera() {
    // IMMEDIATELY stop processing
    isProcessing = false;
    
    // Stop the camera stream
    if (cameraStream) {
        cameraStream.getTracks().forEach(track => track.stop());
        cameraStream = null;
    }
    
    // Cancel any in-flight requests
    if (detectionAbortController) {
        detectionAbortController.abort();
        detectionAbortController = null;
    }
    
    // Clear intervals - use clearTimeout for setTimeout timers
    if (runtimeIntervalId) {
        clearTimeout(runtimeIntervalId);  // Changed from clearInterval to clearTimeout
        runtimeIntervalId = null;
    }
    if (processingIntervalId) {
        clearTimeout(processingIntervalId);
        processingIntervalId = null;
    }
    
    cameraVideo.srcObject = null;
    cameraContainer.classList.add('hidden');
    startCameraBtn.classList.remove('hidden');
    stopCameraBtn.classList.add('hidden');
    
    // Automatically save report when camera stops
    await saveCameraReport();
    
    console.log('✓ Camera stopped completely and report saved');
}

// Frame counter for skipping frames
let frameCount = 0;
const FRAME_SKIP = 2; // Process every 3rd frame (0, skip, skip, 3, skip, skip...)
const TARGET_FPS = 10; // Process at max 10 FPS
const FRAME_DELAY = 1000 / TARGET_FPS; // ~100ms per frame

async function processCamera() {
    if (!cameraStream || !isProcessing) {
        console.log('⏹️ Processing stopped (stream/processing check)');
        return;
    }
    
    try {
        // Check video dimensions
        if (cameraVideo.videoWidth === 0 || cameraVideo.videoHeight === 0) {
            console.warn('⏳ Video dimensions not ready yet');
            if (cameraStream && isProcessing) {
                processingIntervalId = setTimeout(processCamera, 500);
            }
            return;
        }
        
        // Frame skipping - only process every Nth frame
        frameCount++;
        if (frameCount % FRAME_SKIP !== 0) {
            if (cameraStream && isProcessing) {
                processingIntervalId = setTimeout(processCamera, 50);
            }
            return;
        }
        
        // Initialize canvas
        const ctx = cameraCanvas.getContext('2d');
        if (!ctx) {
            console.error('❌ Failed to get canvas context');
            return;
        }
        
        // Resize canvas to smaller size for faster processing (mobile optimization)
        const targetWidth = 480;  // Reduce from full resolution to 480px
        const targetHeight = 640; // Reduce from full resolution
        const aspectRatio = cameraVideo.videoWidth / cameraVideo.videoHeight;
        
        let drawWidth = targetWidth;
        let drawHeight = Math.round(targetWidth / aspectRatio);
        
        if (drawHeight > targetHeight) {
            drawHeight = targetHeight;
            drawWidth = Math.round(targetHeight * aspectRatio);
        }
        
        // Set canvas size to smaller dimensions
        cameraCanvas.width = drawWidth;
        cameraCanvas.height = drawHeight;
        
        // Draw video frame to canvas with reduced size
        try {
            ctx.drawImage(cameraVideo, 0, 0, drawWidth, drawHeight);
        } catch (drawError) {
            console.error('❌ drawImage failed:', drawError);
            if (cameraStream && isProcessing) {
                processingIntervalId = setTimeout(processCamera, FRAME_DELAY);
            }
            return;
        }
        
        // Convert canvas to base64 JPEG with LOW quality for faster transmission
        let imageData;
        try {
            // Reduced quality to 0.5 for faster encoding and transmission
            imageData = cameraCanvas.toDataURL('image/jpeg', 0.5);
        } catch (toDataURLError) {
            console.error('❌ toDataURL failed:', toDataURLError);
            if (cameraStream && isProcessing) {
                processingIntervalId = setTimeout(processCamera, FRAME_DELAY);
            }
            return;
        }
        
        // Validate data URL format
        if (!imageData) {
            console.error('❌ toDataURL returned null');
            if (cameraStream && isProcessing) {
                processingIntervalId = setTimeout(processCamera, FRAME_DELAY);
            }
            return;
        }
        
        // Extract base64 part
        let base64Data;
        if (imageData.includes(',')) {
            base64Data = imageData.split(',')[1];
        } else {
            base64Data = imageData;
        }
        
        // Validate base64 data
        if (!base64Data || base64Data.length === 0) {
            console.error('❌ Base64 data is empty after extraction');
            if (cameraStream && isProcessing) {
                processingIntervalId = setTimeout(processCamera, FRAME_DELAY);
            }
            return;
        }
        
        if (base64Data.length < 50) {
            console.warn(`⚠️ Base64 data seems too small: ${base64Data.length} characters`);
            if (cameraStream && isProcessing) {
                processingIntervalId = setTimeout(processCamera, FRAME_DELAY);
            }
            return;
        }
        
        // Check if we should continue processing
        if (!isProcessing) {
            console.log('⏹️ Stop signal received before sending request');
            return;
        }
        
        console.log(`📤 Sending frame ${frameCount} (size: ${Math.round(base64Data.length / 1024)}KB)`);
        
        // Send frame to server for detection with abort signal
        const response = await fetch('/detect-frame', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                image: imageData
            }),
            signal: detectionAbortController.signal  // Cancel if stopCamera() is called
        });
        
        // Check again after fetch
        if (!isProcessing) {
            console.log('⏹️ Stop signal received after response');
            return;
        }
        
        if (!response.ok) {
            const errorData = await response.json();
            console.error(`❌ Server error ${response.status}:`, errorData.error);
            if (cameraStream && isProcessing) {
                processingIntervalId = setTimeout(processCamera, FRAME_DELAY);
            }
            return;
        }
        
        const data = await response.json();
        
        if (!isProcessing) {
            console.log('⏹️ Stop signal received after parsing JSON');
            return;
        }
        
        if (!data.success) {
            console.warn('⚠️ Detection returned false success:', data.error);
            if (cameraStream && isProcessing) {
                processingIntervalId = setTimeout(processCamera, 500);
            }
            return;
        }
        
        // Draw boxes on canvas if detections found
        if (data.boxes && data.boxes.length > 0) {
            const ctx = cameraCanvas.getContext('2d');
            
            // Redraw current frame
            ctx.drawImage(cameraVideo, 0, 0, cameraCanvas.width, cameraCanvas.height);
            
            // Draw bounding boxes
            data.boxes.forEach(box => {
                // Draw rectangle with bright cyan color
                ctx.strokeStyle = '#00FFFF';
                ctx.lineWidth = 3;
                ctx.strokeRect(box.x1, box.y1, box.x2 - box.x1, box.y2 - box.y1);
                
                // Draw filled background for text
                const label = `ID: ${box.id} (${box.confidence})`;
                ctx.font = 'bold 14px Arial';
                const textMetrics = ctx.measureText(label);
                const textWidth = textMetrics.width;
                const textHeight = 20;
                
                ctx.fillStyle = '#00FFFF';
                ctx.fillRect(box.x1, box.y1 - textHeight - 4, textWidth + 8, textHeight);
                
                // Draw text
                ctx.fillStyle = '#000000';
                ctx.fillText(label, box.x1 + 4, box.y1 - 6);
            });
            
            console.log(`✓ Drew ${data.boxes.length} boxes on canvas`);
        }
        
        if (data.pothole_count > 0) {
            totalDetections += data.pothole_count;
            
            if (data.pothole_ids) {
                data.pothole_ids.forEach(id => {
                    // Add new unique pothole ID and capture location
                    if (!uniquePotholeIds.has(id)) {
                        uniquePotholeIds.add(id);
                        // Capture location for this new unique pothole
                        capturePotholeLocation(id);
                    }
                });
            }
            
            console.log(`✓ Found ${data.pothole_count} pothole(s), Unique: ${data.unique_count}`);
        }
        
        detectionCountSpan.textContent = totalDetections;
        uniqueIdsSpan.textContent = data.unique_count || uniquePotholeIds.size;
        
    } catch (error) {
        // Ignore abort errors - this is expected when stopping
        if (error.name === 'AbortError') {
            console.log('⏹️ Request aborted due to camera stop');
            return;
        }
        console.error('❌ Error processing frame:', error);
    }
    
    // Only schedule next frame if still processing
    if (cameraStream && isProcessing && detectionAbortController) {
        processingIntervalId = setTimeout(processCamera, 500);
    }
}

function capturePotholeLocation(potholeId) {
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            (position) => {
                const lat = position.coords.latitude;
                const lng = position.coords.longitude;
                
                // Store the location
                detectedPotholeLocations[potholeId] = {
                    lat: lat,
                    lng: lng,
                    timestamp: new Date().toLocaleTimeString()
                };
                
                // Add marker to map
                addPotholeMarkerToMap(potholeId, lat, lng);
                
                // Update locations list
                updateLocationsListDisplay();
                
                console.log(`📍 Pothole ${potholeId} detected at: ${lat.toFixed(4)}, ${lng.toFixed(4)}`);
            },
            (error) => {
                console.warn(`⚠️ Could not get location for pothole ${potholeId}:`, error.message);
            }
        );
    }
}

function addPotholeMarkerToMap(potholeId, lat, lng) {
    if (!cameraLocationMap) return;
    
    // Remove old marker if exists
    if (potholeLocationMarkers[potholeId]) {
        cameraLocationMap.removeLayer(potholeLocationMarkers[potholeId]);
    }
    
    // Create marker with custom color based on pothole ID
    const colors = ['red', 'blue', 'green', 'purple', 'orange', 'darkred', 'darkblue', 'darkgreen'];
    const colorIndex = potholeId % colors.length;
    
    const marker = L.marker([lat, lng], {
        title: `Pothole ${potholeId}`
    }).bindPopup(`<b>Pothole ${potholeId}</b><br>Lat: ${lat.toFixed(4)}<br>Lng: ${lng.toFixed(4)}<br>Time: ${new Date().toLocaleTimeString()}`);
    
    marker.addTo(cameraLocationMap);
    potholeLocationMarkers[potholeId] = marker;
    
    // Fit map to show all markers
    const bounds = L.latLngBounds(Object.values(detectedPotholeLocations).map(loc => [loc.lat, loc.lng]));
    if (bounds.isValid()) {
        cameraLocationMap.fitBounds(bounds, { padding: [50, 50] });
    }
}

function updateLocationsListDisplay() {
    const locationsList = document.getElementById('camera-locations-list');
    
    if (Object.keys(detectedPotholeLocations).length === 0) {
        locationsList.innerHTML = '<div class="locations-list empty">No potholes detected yet</div>';
        return;
    }
    
    const locationsHtml = Object.entries(detectedPotholeLocations)
        .sort(([idA], [idB]) => parseInt(idA) - parseInt(idB))
        .map(([id, location]) => `
            <div class="location-item">
                <span class="location-item-id">P${id}</span>
                <strong>Latitude:</strong> ${location.lat.toFixed(6)} | 
                <strong>Longitude:</strong> ${location.lng.toFixed(6)} | 
                <strong>Time:</strong> ${location.timestamp}
            </div>
        `)
        .join('');
    
    locationsList.innerHTML = locationsHtml;
}

function updateRuntime() {
    // Stop immediately if camera is not running
    if (!isProcessing || !cameraStream) {
        return;
    }
    
    if (startTime) {
        const elapsed = Math.floor((Date.now() - startTime) / 1000);
        runtimeSpan.textContent = elapsed + 's';
        
        // Only schedule next update if still processing
        if (isProcessing && cameraStream) {
            runtimeIntervalId = setTimeout(updateRuntime, 1000);
        }
    }
}

async function saveCameraReport() {
    const elapsed = Math.floor((Date.now() - startTime) / 1000);
    
    const reportData = {
        timestamp: new Date().toLocaleString(),
        total_detections: totalDetections,
        unique_potholes: uniquePotholeIds.size,
        runtime_seconds: elapsed,
        pothole_locations: detectedPotholeLocations
    };
    
    try {
        const response = await fetch('/save-camera-report', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(reportData)
        });
        
        if (response.ok) {
            const data = await response.json();
            let detailsMsg = 'Detections: ' + totalDetections + '\nUnique Potholes: ' + uniquePotholeIds.size + '\nRuntime: ' + elapsed + 's';
            
            // Add location info if available
            if (Object.keys(detectedPotholeLocations).length > 0) {
                detailsMsg += '\nLocations Captured: ' + Object.keys(detectedPotholeLocations).length;
            }
            
            alert('✓ Report saved successfully!\n\n' + detailsMsg);
        } else {
            showCameraError('Failed to save report');
        }
    } catch (error) {
        showCameraError('Error saving report: ' + error.message);
    }
}

function showCameraError(message) {
    cameraError.textContent = message;
    cameraError.classList.remove('hidden');
}
