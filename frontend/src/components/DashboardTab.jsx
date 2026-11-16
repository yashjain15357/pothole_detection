import React, { useEffect, useState, useRef } from 'react';
import { 
  BarChart3, 
  Layers, 
  AlertTriangle, 
  Image as ImageIcon, 
  Video, 
  Camera, 
  RefreshCw,
  TrendingUp,
  Clock
} from 'lucide-react';
import { Chart, registerables } from 'chart.js';
import { apiUrl, safeFetchJson } from '../apiConfig';

Chart.register(...registerables);

export default function DashboardTab({ onViewReport }) {
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const typeChartRef = useRef(null);
  const trendChartRef = useRef(null);
  const typeChartInstance = useRef(null);
  const trendChartInstance = useRef(null);

  const fetchAnalytics = async () => {
    setLoading(true);
    setError('');
    try {
      const { response: res, data } = await safeFetchJson(apiUrl('/api/dashboard/analytics'), {
        headers: { 'Accept': 'application/json' },
        credentials: 'include'
      });
      if (res.ok && data.success) {
        setAnalytics(data);
      } else {
        setError(data.error || 'Failed to load analytics');
      }
    } catch (err) {
      setError('Error connecting to analytics service');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAnalytics();
  }, []);

  // Render Charts
  useEffect(() => {
    if (!analytics) return;

    // 1. Doughnut chart: reports by type
    if (typeChartRef.current) {
      if (typeChartInstance.current) {
        typeChartInstance.current.destroy();
      }

      const byType = analytics.by_type || {};
      const labels = Object.keys(byType).map(t => t.toUpperCase());
      const values = Object.values(byType);

      typeChartInstance.current = new Chart(typeChartRef.current, {
        type: 'doughnut',
        data: {
          labels: labels.length ? labels : ['No Data'],
          datasets: [{
            data: values.length ? values : [1],
            backgroundColor: ['#4f46e5', '#f59e0b', '#ec4899', '#10b981'],
            borderWidth: 2,
            borderColor: '#ffffff',
          }],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { position: 'bottom' },
          },
        },
      });
    }

    // 2. Bar / Line chart: Daily reports trend
    if (trendChartRef.current) {
      if (trendChartInstance.current) {
        trendChartInstance.current.destroy();
      }

      const daily = analytics.daily_reports || {};
      const dates = Object.keys(daily);
      const counts = Object.values(daily);

      trendChartInstance.current = new Chart(trendChartRef.current, {
        type: 'bar',
        data: {
          labels: dates.length ? dates : ['Past 7 Days'],
          datasets: [{
            label: 'Incidents Logged',
            data: counts.length ? counts : [0],
            backgroundColor: '#06b6d4',
            borderRadius: 6,
          }],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          scales: {
            y: { beginAtZero: true, ticks: { stepSize: 1 } },
          },
          plugins: {
            legend: { display: false },
          },
        },
      });
    }

    return () => {
      if (typeChartInstance.current) typeChartInstance.current.destroy();
      if (trendChartInstance.current) trendChartInstance.current.destroy();
    };
  }, [analytics]);

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', padding: '60px' }}>
        <div className="spinner" style={{ borderColor: '#cbd5e1', borderTopColor: '#4f46e5', width: '36px', height: '36px' }} />
      </div>
    );
  }

  const byType = analytics?.by_type || {};

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '24px' }}>
        <div>
          <h2 style={{ fontSize: '1.5rem', fontWeight: 800, color: '#0f172a' }}>Overview & Analytics</h2>
          <p style={{ color: '#64748b', fontSize: '0.9rem' }}>Real-time statistics of reported road damages across the city</p>
        </div>

        <button onClick={fetchAnalytics} className="btn btn-secondary">
          <RefreshCw size={16} />
          Refresh Stats
        </button>
      </div>

      {error && (
        <div style={{ background: '#fef2f2', color: '#b91c1c', padding: '14px', borderRadius: '8px', marginBottom: '20px' }}>
          {error}
        </div>
      )}

      {/* KPI Cards */}
      <div className="summary-grid">
        <div className="summary-card">
          <div className="summary-icon-box" style={{ background: '#eef2ff', color: '#4f46e5' }}>
            <Layers size={24} />
          </div>
          <div className="summary-content">
            <h3>Total Reports</h3>
            <p className="summary-value">{analytics?.total_reports || 0}</p>
          </div>
        </div>

        <div className="summary-card">
          <div className="summary-icon-box" style={{ background: '#fef2f2', color: '#ef4444' }}>
            <AlertTriangle size={24} />
          </div>
          <div className="summary-content">
            <h3>Potholes Found</h3>
            <p className="summary-value">{analytics?.total_potholes || 0}</p>
          </div>
        </div>

        <div className="summary-card">
          <div className="summary-icon-box" style={{ background: '#e0f2fe', color: '#0284c7' }}>
            <ImageIcon size={24} />
          </div>
          <div className="summary-content">
            <h3>Image Scans</h3>
            <p className="summary-value">{byType['image'] || 0}</p>
          </div>
        </div>

        <div className="summary-card">
          <div className="summary-icon-box" style={{ background: '#fef3c7', color: '#d97706' }}>
            <Video size={24} />
          </div>
          <div className="summary-content">
            <h3>Video Scans</h3>
            <p className="summary-value">{byType['video'] || 0}</p>
          </div>
        </div>

        <div className="summary-card">
          <div className="summary-icon-box" style={{ background: '#fce7f3', color: '#db2777' }}>
            <Camera size={24} />
          </div>
          <div className="summary-content">
            <h3>Live Cam Scans</h3>
            <p className="summary-value">{byType['camera'] || 0}</p>
          </div>
        </div>
      </div>

      {/* Charts Section */}
      <div className="charts-grid">
        <div className="card">
          <div className="card-header">
            <h3 className="card-title">
              <BarChart3 size={20} color="#4f46e5" />
              Reports Distribution by Source
            </h3>
          </div>
          <div className="chart-wrapper">
            <canvas ref={typeChartRef} />
          </div>
        </div>

        <div className="card">
          <div className="card-header">
            <h3 className="card-title">
              <TrendingUp size={20} color="#06b6d4" />
              Daily Detection Frequency
            </h3>
          </div>
          <div className="chart-wrapper">
            <canvas ref={trendChartRef} />
          </div>
        </div>
      </div>

      {/* High Pothole Count Incidents */}
      <div className="card">
        <div className="card-header">
          <h3 className="card-title">
            <AlertTriangle size={20} color="#ef4444" />
            Severe Pothole Clusters (Top High Count Reports)
          </h3>
        </div>

        <div className="table-responsive">
          <table>
            <thead>
              <tr>
                <th>Report ID</th>
                <th>Source Type</th>
                <th>File / Title</th>
                <th>Potholes Count</th>
                <th>Date Logged</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {(analytics?.top_reports || []).length === 0 ? (
                <tr>
                  <td colSpan="6" style={{ textAlign: 'center', color: '#94a3b8', padding: '24px' }}>
                    No report records logged yet.
                  </td>
                </tr>
              ) : (
                analytics.top_reports.map((r) => (
                  <tr key={r.id}>
                    <td><strong>#{r.id}</strong></td>
                    <td>
                      <span className={`badge badge-${r.type}`}>
                        {r.type}
                      </span>
                    </td>
                    <td>{r.name}</td>
                    <td>
                      <span style={{ fontWeight: 700, color: r.count > 5 ? '#ef4444' : '#f59e0b' }}>
                        {r.count} potholes
                      </span>
                    </td>
                    <td>
                      <span style={{ display: 'flex', alignItems: 'center', gap: '4px', color: '#64748b' }}>
                        <Clock size={14} /> {r.date}
                      </span>
                    </td>
                    <td>
                      <button
                        onClick={() => onViewReport(r.id)}
                        className="btn btn-secondary"
                        style={{ padding: '4px 10px', fontSize: '0.8rem' }}
                      >
                        Inspect
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
