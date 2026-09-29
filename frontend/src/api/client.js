import axios from 'axios';
import { notifySaved } from '../components/notifications';
export const API_BASE = (
  import.meta.env.VITE_API_BASE_URL || '/api/v1'
).replace(/\/$/, '');
let csrfToken = null;
export function setCsrf(token) {
  csrfToken = token;
}
export const api = axios.create({ baseURL: API_BASE, timeout: 30000, withCredentials: true });
api.interceptors.request.use((config) => {
  if (csrfToken && !['get', 'head', 'options'].includes(config.method))
    config.headers['X-CSRF-Token'] = csrfToken;
  return config;
});
export function normalizeError(error) {
  const body = error.response?.data;
  return Object.assign(new Error(body?.message || error.message || 'Request failed'), {
    code: body?.code || 'network_error',
    field_errors: body?.field_errors || {},
    status: error.response?.status,
  });
}
api.interceptors.response.use(
  (response) => {
    notifySaved(response.config);
    return response.config.responseType === 'blob' ? response.data : response.data.data;
  },
  async (error) => {
    if (error.response?.data instanceof Blob) {
      try {
        error.response.data = JSON.parse(await error.response.data.text());
      } catch {
        /* Keep transport error. */
      }
    }
    const normalized = normalizeError(error);
    if ([401, 403].includes(normalized.status) && !error.config?.skipAuthEvent) {
      if (normalized.status === 401) csrfToken = null;
      window.dispatchEvent(new CustomEvent('api-auth', { detail: normalized.status }));
    }
    return Promise.reject(normalized);
  },
);
export function downloadBlob(blob, name) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = name;
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
