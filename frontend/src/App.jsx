import React, { useState, useEffect } from 'react';
import Navbar from './components/Navbar';
import Login from './components/Login';
import DashboardTab from './components/DashboardTab';
import ImageDetectionTab from './components/ImageDetectionTab';
import VideoDetectionTab from './components/VideoDetectionTab';
import LiveCameraTab from './components/LiveCameraTab';
import ReportsTab from './components/ReportsTab';
import { apiUrl, safeFetchJson } from './apiConfig';

export default function App() {
  const [user, setUser] = useState(null);
  const [checkingAuth, setCheckingAuth] = useState(true);
  const [activeTab, setActiveTab] = useState('dashboard');
  const [selectedReportId, setSelectedReportId] = useState(null);
  const [toasts, setToasts] = useState([]);

  // Check login status on launch
  useEffect(() => {
    const checkAuthStatus = async () => {
      try {
        const { response, data } = await safeFetchJson(apiUrl('/api/session'), {
          headers: { 'Accept': 'application/json' },
          credentials: 'include',
        });
        if (response.ok && data.authenticated && data.user) {
          setUser({
            user_id: data.user.id,
            username: data.user.username,
            full_name: data.user.full_name,
            email: data.user.email,
            role: data.user.role,
          });
        } else {
          setUser(null);
        }
      } catch (err) {
        setUser(null);
      } finally {
        setCheckingAuth(false);
      }
    };

    checkAuthStatus();
  }, []);

  const addToast = (message, type = 'success') => {
    const id = Date.now();
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 4000);
  };

  const handleLogout = async () => {
    try {
      await safeFetchJson(apiUrl('/logout'), {
        method: 'POST',
        headers: { 'Accept': 'application/json' },
        credentials: 'include',
      });
    } catch (err) {
      // ignore
    } finally {
      if (typeof window !== 'undefined') {
        localStorage.removeItem('auth_token');
      }
      setUser(null);
      addToast('Logged out successfully', 'success');
    }
  };

  const handleViewReportFromDashboard = (reportId) => {
    setSelectedReportId(reportId);
    setActiveTab('reports');
  };

  if (checkingAuth) {
    return (
      <div style={{
        height: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: '#f8fafc'
      }}>
        <div className="spinner" style={{ borderColor: '#cbd5e1', borderTopColor: '#4f46e5', width: '36px', height: '36px' }} />
      </div>
    );
  }

  if (!user) {
    return <Login onLoginSuccess={(u, options = {}) => {
      setUser({
        user_id: u.id || u.user_id || u.username,
        username: u.username || u.user_id || 'user',
        full_name: u.full_name || u.username || u.user_id || 'User',
        email: u.email || '',
        role: u.role || 'user',
      });
      if (options?.message) {
        addToast(options.message, 'success');
      }
    }} />;
  }

  return (
    <div className="app-container">
      <Navbar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        user={user}
        onLogout={handleLogout}
      />

      <main className="main-content">
        {activeTab === 'dashboard' && (
          <DashboardTab onViewReport={handleViewReportFromDashboard} />
        )}

        {activeTab === 'image' && (
          <ImageDetectionTab onToast={addToast} />
        )}

        {activeTab === 'video' && (
          <VideoDetectionTab onToast={addToast} />
        )}

        {activeTab === 'camera' && (
          <LiveCameraTab onToast={addToast} />
        )}

        {activeTab === 'reports' && (
          <ReportsTab
            selectedReportId={selectedReportId}
            onClearSelectedReportId={() => setSelectedReportId(null)}
            onToast={addToast}
          />
        )}
      </main>

      {/* Floating Toast Notification Bar */}
      <div className="toast-container">
        {toasts.map((toast) => (
          <div key={toast.id} className={`toast toast-${toast.type}`}>
            <span>{toast.message}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
