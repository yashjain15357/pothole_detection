import React, { useEffect, useRef, useState } from 'react';
import { MapPin, Navigation, Edit3, Crosshair } from 'lucide-react';
import L from 'leaflet';

export default function LeafletMapPicker({ 
  latitude, 
  longitude, 
  onLocationChange, 
  height = '320px' 
}) {
  const mapContainerRef = useRef(null);
  const mapInstanceRef = useRef(null);
  const markerRef = useRef(null);

  const [inputLat, setInputLat] = useState(latitude ? String(latitude) : '23.5183');
  const [inputLng, setInputLng] = useState(longitude ? String(longitude) : '77.8128');
  const [locationSource, setLocationSource] = useState('Custom Pin / Map');

  const defaultLat = latitude || 23.5183;
  const defaultLng = longitude || 77.8128;

  useEffect(() => {
    if (!mapContainerRef.current) return;

    delete L.Icon.Default.prototype._getIconUrl;
    L.Icon.Default.mergeOptions({
      iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
      iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
      shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
    });

    if (!mapInstanceRef.current) {
      const map = L.map(mapContainerRef.current).setView([defaultLat, defaultLng], 14);
      mapInstanceRef.current = map;

      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap contributors',
        maxZoom: 19,
      }).addTo(map);

      const marker = L.marker([defaultLat, defaultLng], { draggable: true }).addTo(map);
      markerRef.current = marker;

      // Drag event
      marker.on('dragend', () => {
        const pos = marker.getLatLng();
        setInputLat(pos.lat.toFixed(6));
        setInputLng(pos.lng.toFixed(6));
        setLocationSource('Custom Dragged Pin');
        onLocationChange(pos.lat, pos.lng);
      });

      // Click event
      map.on('click', (e) => {
        const { lat, lng } = e.latlng;
        marker.setLatLng([lat, lng]);
        setInputLat(lat.toFixed(6));
        setInputLng(lng.toFixed(6));
        setLocationSource('Custom Clicked Location');
        onLocationChange(lat, lng);
      });
    }

    return () => {
      if (mapInstanceRef.current) {
        mapInstanceRef.current.remove();
        mapInstanceRef.current = null;
      }
    };
  }, []);

  // Sync marker position when external props change
  useEffect(() => {
    if (latitude && longitude) {
      setInputLat(Number(latitude).toFixed(6));
      setInputLng(Number(longitude).toFixed(6));
      if (markerRef.current && mapInstanceRef.current) {
        markerRef.current.setLatLng([latitude, longitude]);
      }
    }
  }, [latitude, longitude]);

  // Handle manual coordinate changes from inputs
  const handleManualApply = (e) => {
    e.preventDefault();
    const lat = parseFloat(inputLat);
    const lng = parseFloat(inputLng);

    if (isNaN(lat) || isNaN(lng) || lat < -90 || lat > 90 || lng < -180 || lng > 180) {
      alert('Please enter valid coordinates (-90 to 90 for Lat, -180 to 180 for Lng)');
      return;
    }

    setLocationSource('Custom Manual Entry');
    onLocationChange(lat, lng);
    if (markerRef.current && mapInstanceRef.current) {
      markerRef.current.setLatLng([lat, lng]);
      mapInstanceRef.current.setView([lat, lng], 15);
    }
  };

  // Explicit GPS location
  const handleGetCurrentLocation = () => {
    if (!navigator.geolocation) {
      alert('Geolocation is not supported by your browser');
      return;
    }

    navigator.geolocation.getCurrentPosition(
      (position) => {
        const lat = position.coords.latitude;
        const lng = position.coords.longitude;
        setInputLat(lat.toFixed(6));
        setInputLng(lng.toFixed(6));
        setLocationSource('Current Device GPS');
        onLocationChange(lat, lng);
        if (markerRef.current && mapInstanceRef.current) {
          markerRef.current.setLatLng([lat, lng]);
          mapInstanceRef.current.setView([lat, lng], 16);
        }
      },
      (error) => {
        alert('Could not get GPS location: ' + error.message);
      },
      { enableHighAccuracy: true, timeout: 10000 }
    );
  };

  return (
    <div style={{ position: 'relative' }}>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '8px',
        marginBottom: '10px'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.85rem', color: '#334155' }}>
          <MapPin size={16} color="#4f46e5" />
          <span><strong>Click map</strong> or <strong>drag pin</strong> to choose exact road location</span>
        </div>

        <button
          type="button"
          onClick={handleGetCurrentLocation}
          className="btn btn-secondary"
          style={{ padding: '6px 12px', fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '6px' }}
        >
          <Navigation size={14} color="#06b6d4" />
          Use Current GPS
        </button>
      </div>

      {/* Leaflet Map Box */}
      <div
        ref={mapContainerRef}
        style={{
          height,
          width: '100%',
          borderRadius: '10px',
          border: '1px solid #cbd5e1',
          zIndex: 1
        }}
      />

      {/* Manual Coordinates Input & Source Status */}
      <form onSubmit={handleManualApply} style={{
        marginTop: '12px',
        background: '#f8fafc',
        padding: '12px 14px',
        borderRadius: '8px',
        border: '1px solid #e2e8f0',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '12px'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <label style={{ fontSize: '0.78rem', fontWeight: 700, color: '#475569' }}>LAT:</label>
            <input
              type="number"
              step="any"
              value={inputLat}
              onChange={(e) => setInputLat(e.target.value)}
              placeholder="e.g. 23.5183"
              style={{
                width: '110px',
                padding: '6px 8px',
                borderRadius: '6px',
                border: '1px solid #cbd5e1',
                fontSize: '0.85rem'
              }}
            />
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <label style={{ fontSize: '0.78rem', fontWeight: 700, color: '#475569' }}>LNG:</label>
            <input
              type="number"
              step="any"
              value={inputLng}
              onChange={(e) => setInputLng(e.target.value)}
              placeholder="e.g. 77.8128"
              style={{
                width: '110px',
                padding: '6px 8px',
                borderRadius: '6px',
                border: '1px solid #cbd5e1',
                fontSize: '0.85rem'
              }}
            />
          </div>

          <button
            type="submit"
            className="btn btn-secondary"
            style={{ padding: '6px 12px', fontSize: '0.8rem' }}
          >
            <Crosshair size={14} /> Update Pin
          </button>
        </div>

        <div style={{ fontSize: '0.78rem', color: '#64748b', display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span style={{
            display: 'inline-block',
            width: '8px',
            height: '8px',
            borderRadius: '50%',
            background: locationSource.includes('GPS') ? '#10b981' : '#4f46e5'
          }} />
          <span>{locationSource}</span>
        </div>
      </form>
    </div>
  );
}
