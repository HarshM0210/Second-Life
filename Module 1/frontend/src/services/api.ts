import axios from "axios";

/**
 * Base Axios instance configured to communicate with the FastAPI backend.
 * In development, Vite proxies /api requests to http://localhost:8000.
 * In production, set VITE_API_BASE_URL to the backend origin.
 */
const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "/api",
  headers: {
    "Content-Type": "application/json",
  },
  timeout: 10000, // 10s — generous for the 2s pipeline budget
});

// Response interceptor for centralized error handling
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    // Let callers handle specific HTTP status codes
    return Promise.reject(error);
  },
);

export default apiClient;
