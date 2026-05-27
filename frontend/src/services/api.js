import axios from 'axios';

const IS_DEV = import.meta.env.DEV;
const API_URL = IS_DEV ? 'http://127.0.0.1:8000' : `${window.location.origin}/api`;

const api = axios.create({
  baseURL: API_URL,
  headers: { 'Content-Type': 'application/json' },
});

// Attach JWT token to every request if available
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('anpr_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Dashboard
export const getDashboard = async () => {
  const response = await api.get('/dashboard');
  return response.data;
};

// Vehicle
export const addVehicle = async (plateNumber) => {
  const response = await api.post(`/vehicle?plate_number=${encodeURIComponent(plateNumber)}`);
  return response.data;
};

// Manual Entry / Exit
export const recordEntry = async (plateNumber) => {
  const response = await api.post(`/entry?plate_number=${encodeURIComponent(plateNumber)}`);
  return response.data;
};

export const recordExit = async (plateNumber, bypassPayment = false, triggerGate = true) => {
  const response = await api.post(`/exit?plate_number=${encodeURIComponent(plateNumber)}&bypass_payment=${bypassPayment}&trigger_gate=${triggerGate}`);
  return response.data;
};

// ---------- Multi-Camera Live ANPR ----------

// Camera management
export const getCameras = async () => {
  const response = await api.get('/live/cameras');
  return response.data;
};

export const startLiveFeed = async (source = 'sample.mp4', cameraId = 1, label = 'Camera 1') => {
  const response = await api.get(
    `/live/start?source=${encodeURIComponent(source)}&camera_id=${cameraId}&label=${encodeURIComponent(label)}`
  );
  return response.data;
};

export const stopLiveFeed = async (cameraId = 1) => {
  const response = await api.get(`/live/stop?camera_id=${cameraId}`);
  return response.data;
};

export const stopAllFeeds = async () => {
  const response = await api.get('/live/stop-all');
  return response.data;
};

// Stream URL builder (per camera)
export const getStreamUrl = (cameraId = 1) => `${API_URL}/live/stream?camera_id=${cameraId}`;

// Legacy constant for backward compat
export const STREAM_URL = getStreamUrl(1);

// Detections
export const getLiveDetections = async (limit = 50, cameraId = null) => {
  const params = [`limit=${limit}`];
  if (cameraId) params.push(`camera_id=${cameraId}`);
  const response = await api.get(`/live/detections?${params.join('&')}`);
  return response.data;
};

export const clearLiveDetections = async (cameraId = null) => {
  const params = cameraId ? `?camera_id=${cameraId}` : '';
  const response = await api.delete(`/live/detections${params}`);
  return response.data;
};

// Entry / Exit actions (unchanged — they operate on plate data)
export const registerLiveEntry = async (plateNumber, plateImageUrl = '', vehicleImageUrl = '') => {
  const response = await api.post(
    `/live/register-entry?plate_number=${encodeURIComponent(plateNumber)}&plate_image_url=${encodeURIComponent(plateImageUrl)}&vehicle_image_url=${encodeURIComponent(vehicleImageUrl)}`
  );
  return response.data;
};

export const approveExit = async (plateNumber) => {
  const response = await api.post(
    `/live/approve-exit?plate_number=${encodeURIComponent(plateNumber)}`
  );
  return response.data;
};

// Audit Logs
export const getAuditLogs = async (limit = 50) => {
  const response = await api.get(`/audit-logs?limit=${limit}`);
  return response.data;
};

export const clearAuditLogs = async () => {
  const response = await api.delete('/audit-logs');
  return response.data;
};

// Reports
export const getReports = async (timeframe = 'today') => {
  const response = await api.get(`/reports?timeframe=${timeframe}`);
  return response.data;
};

// Monitoring
export const getMonitoringMetrics = async () => {
  const response = await api.get('/live/monitoring-metrics');
  return response.data;
};

export default api;
