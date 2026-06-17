import axios from "axios";

const baseURL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api/v1";

export const client = axios.create({
  baseURL,
});

// Mocks are disabled for production/live demo
client.interceptors.request.use(async (config) => {
  return config;
});
