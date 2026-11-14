import React from 'react';
import { 
  BarChart3, 
  Image as ImageIcon, 
  Video, 
  Camera, 
  FileText, 
  LogOut, 
  ShieldAlert 
} from 'lucide-react';

export default function Navbar({ activeTab, setActiveTab, user, onLogout }) {
  const tabs = [
    { id: 'dashboard', label: 'Dashboard', icon: BarChart3 },
    { id: 'image', label: 'Image Detection', icon: ImageIcon },
    { id: 'video', label: 'Video Detection', icon: Video },
    { id: 'camera', label: 'Live Camera', icon: Camera },
    { id: 'reports', label: 'Reports', icon: FileText },
  ];

  return (
    <header className="app-header">
      <div className="header-inner">
        <div className="brand-section">
          <div className="brand-logo">
            <ShieldAlert size={26} />
          </div>
          <div>
            <h1 className="brand-title">FIX MY CITY</h1>
            <p className="brand-subtitle">AI-Powered Road Pothole Detection & Geotagging</p>
          </div>
        </div>

        <div className="user-section">
          <div className="user-badge">
            <div className="user-avatar-circle">
              {(user?.username || 'U')[0].toUpperCase()}
            </div>
            <span>{user?.username || 'User'}</span>
          </div>

          <button onClick={onLogout} className="logout-button" title="Log Out">
            <LogOut size={16} />
            <span>Logout</span>
          </button>
        </div>
      </div>

      <div className="nav-tabs-wrapper">
        <nav className="nav-tabs">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`nav-tab-btn ${isActive ? 'active' : ''}`}
              >
                <Icon size={18} />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </nav>
      </div>
    </header>
  );
}
