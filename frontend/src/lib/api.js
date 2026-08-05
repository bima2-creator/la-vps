import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API_BASE = `${BACKEND_URL}/api`;

export const api = axios.create({
  baseURL: API_BASE,
  // Non-credentialed requests: the edge/ingress injects `Access-Control-Allow-Origin: *`,
  // which is INVALID together with credentials and gets blocked by browsers on cross-origin
  // (e.g. embedded preview) requests. Auth uses the Bearer token in localStorage (below),
  // so cookies are not needed and withCredentials must stay false to keep CORS valid.
  withCredentials: false,
  headers: { "Content-Type": "application/json" },
});

// Attach bearer token if present (fallback for httpOnly-cookie env quirks).
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("la_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

export function formatApiError(detail) {
  if (detail == null) return "Something went wrong. Please try again.";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail))
    return detail
      .map((e) => (e && typeof e.msg === "string" ? e.msg : JSON.stringify(e)))
      .filter(Boolean)
      .join(" ");
  if (detail && typeof detail.msg === "string") return detail.msg;
  return String(detail);
}
