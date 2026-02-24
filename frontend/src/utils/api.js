import axios from "axios";

export const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

// Auth token utils
export const getToken = () => localStorage.getItem("token");
export const setToken = (t) => localStorage.setItem("token", t || "");
export const clearToken = () => localStorage.removeItem("token");

// Axios setup
axios.defaults.baseURL = API;
axios.interceptors.request.use((config) => {
  const token = getToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

export default axios;
