// Centralized API configuration for Render deployment
// Frontend and backend are served from the same domain on Render,
// so all API requests use relative paths.

export const API_BASE_URL = '';

export function apiUrl(endpoint) {
  const path = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
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
