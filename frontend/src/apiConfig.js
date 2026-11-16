// Centralized API configuration for Render deployment
// Supports:
// 1. Separate Render Static Site (https://pothole-detection-2-sc8w.onrender.com)
// 2. Full-stack deployment on Render backend (https://pothole-detection-1-2csi.onrender.com)
// 3. Local development (localhost / 127.0.0.1 with Vite proxy)

const DEFAULT_BACKEND_URL = 'https://pothole-detection-1-2csi.onrender.com';

function resolveBaseUrl() {
  if (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_API_URL !== undefined) {
    return import.meta.env.VITE_API_URL;
  }
  if (typeof window !== 'undefined') {
    const host = window.location.hostname;
    if (host === 'localhost' || host === '127.0.0.1') {
      return '';
    }
    if (window.location.origin.includes('pothole-detection-1-2csi.onrender.com')) {
      return '';
    }
  }
  return DEFAULT_BACKEND_URL;
}

export const API_BASE_URL = resolveBaseUrl();

export function apiUrl(endpoint) {
  const path = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
  if (!API_BASE_URL) return path;
  return `${API_BASE_URL}${path}`;
}

export async function safeFetchJson(url, options = {}) {
  const headers = { ...(options.headers || {}) };

  // Automatically attach auth token if saved in localStorage
  if (typeof window !== 'undefined') {
    const token = localStorage.getItem('auth_token');
    if (token && !headers['Authorization']) {
      headers['Authorization'] = `Bearer ${token}`;
    }
  }

  const res = await fetch(url, {
    credentials: 'include',
    ...options,
    headers,
  });

  const text = await res.text();
  let data = {};
  if (text && text.trim()) {
    try {
      data = JSON.parse(text);
    } catch (e) {
      throw new Error(`Server returned non-JSON response (${res.status}): ${text.slice(0, 120)}`);
    }
  }
  return { response: res, data };
}
