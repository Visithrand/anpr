import axios from 'axios';

const API_URL = 'http://127.0.0.1:8000';

const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const getDashboard = async () => {
  const response = await api.get('/dashboard');
  return response.data;
};

export const addVehicle = async (plateNumber) => {
  const response = await api.post(`/vehicle?plate_number=${encodeURIComponent(plateNumber)}`);
  return response.data;
};

export const recordEntry = async (plateNumber) => {
  const response = await api.post(`/entry?plate_number=${encodeURIComponent(plateNumber)}`);
  return response.data;
};

export const recordExit = async (plateNumber) => {
  const response = await api.post(`/exit?plate_number=${encodeURIComponent(plateNumber)}`);
  return response.data;
};

export default api;
