import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
});

// Request interceptor: add Bearer token from localStorage
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor: on 401, clear storage and redirect to proper login page
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 401) {
      const role = localStorage.getItem('role');
      const isStaff =
        role === 'auditor' ||
        role === 'admin' ||
        window.location.pathname.startsWith('/auditor') ||
        window.location.pathname.startsWith('/admin');

      localStorage.removeItem('token');
      localStorage.removeItem('role');
      localStorage.removeItem('user');

      const redirectPath = isStaff ? '/auditor/login' : '/login';
      if (window.location.pathname !== redirectPath) {
        window.location.href = redirectPath;
      }
    }
    return Promise.reject(error);
  }
);

export default api;
