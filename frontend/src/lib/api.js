import axios from "axios";
import { useAuthStore } from "../store/auth";
import { useSubscriptionStore } from "../store/subscription";

// Single source of truth for the API base. Overridable at build time via
// VITE_API_BASE; defaults to the same-origin path proxied by Vite (dev) and
// nginx (prod). No API host/path is hardcoded elsewhere in the app.
export const API_BASE = import.meta.env.VITE_API_BASE || "/api/v1";
const REFRESH_URL = `${API_BASE}/auth/refresh/`;

// Single axios instance for the whole app.
const api = axios.create({
  baseURL: API_BASE,
  headers: { "Content-Type": "application/json" },
});

// Attach the access token to every request. For FormData bodies, drop the
// JSON content-type so the browser sets multipart/form-data with a boundary.
api.interceptors.request.use((config) => {
  const token = useAuthStore.getState().access;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  if (typeof FormData !== "undefined" && config.data instanceof FormData) {
    delete config.headers["Content-Type"];
  }
  return config;
});

// On a 401, try a single silent refresh, then replay the request. If refresh
// fails, log the user out.
let refreshing = null;

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config;
    const status = error.response?.status;

    // Subscription gate: any 403 carrying SUBSCRIPTION_EXPIRED locks the app
    // instantly (even mid-session), regardless of which endpoint tripped it.
    if (status === 403 && error.response?.data?.error?.code === "SUBSCRIPTION_EXPIRED") {
      useSubscriptionStore.getState().markExpired(error.response.data.error.message);
    }

    if (status === 401 && !original._retry) {
      original._retry = true;
      const { refresh, setTokens, logout } = useAuthStore.getState();
      if (!refresh) {
        logout();
        return Promise.reject(error);
      }
      try {
        refreshing = refreshing || axios.post(REFRESH_URL, { refresh });
        const { data } = await refreshing;
        refreshing = null;
        setTokens({ access: data.access, refresh: data.refresh ?? refresh });
        original.headers.Authorization = `Bearer ${data.access}`;
        return api(original);
      } catch (e) {
        refreshing = null;
        useAuthStore.getState().logout();
        return Promise.reject(e);
      }
    }
    return Promise.reject(error);
  },
);

// Normalise the backend's consistent error envelope into a readable message.
export function apiError(error, fallback = "Something went wrong.") {
  const data = error?.response?.data;
  if (data?.error?.message) return data.error.message;
  if (typeof data?.detail === "string") return data.detail;
  return fallback;
}

export default api;
