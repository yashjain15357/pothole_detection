// Centralized API configuration
// When deployed on Vercel, requests point directly to your Render backend.
// When running locally on localhost/127.0.0.1, it uses relative path so Vite proxy works.

const DEFAULT_BACKEND_URL = 'https://pothole-detection-1-2csi.onrender.com';

export const API_BASE_URL = (
  typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_API_URL !== undefined
    ? import.meta.env.VITE_API_URL
    : (typeof window !== 'undefined' && (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')
        ? ''
        : DEFAULT_BACKEND_URL)
);

export function apiUrl(endpoint) {
  const path = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
  if (!API_BASE_URL) return path;
  return `${API_BASE_URL}${path}`;
}

export async function safeFetchJson(url, options = {}) {
  const res = await fetch(url, options);
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
