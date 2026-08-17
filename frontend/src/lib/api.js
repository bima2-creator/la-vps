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

// --- Auto-refresh access token on 401 -----------------------------------
// The backend returns both access_token (8h) and refresh_token (7d) in the
// login response body. When an access token expires, transparently exchange
// the refresh token for a new one and retry the original request once.
let _refreshing = null;

async function _doRefresh() {
  const refresh = localStorage.getItem("la_refresh");
  if (!refresh) throw new Error("No refresh token");
  const { data } = await axios.post(
    `${API_BASE}/auth/refresh`,
    { refresh_token: refresh },
    { withCredentials: false, headers: { "Content-Type": "application/json" } }
  );
  if (data.access_token) localStorage.setItem("la_token", data.access_token);
  if (data.refresh_token) localStorage.setItem("la_refresh", data.refresh_token);
  return data.access_token;
}

api.interceptors.response.use(
  (res) => res,
  async (error) => {
    const original = error.config;
    const status = error.response?.status;
    const isAuthRoute =
      original?.url?.includes("/auth/login") ||
      original?.url?.includes("/auth/refresh");
    if (status === 401 && original && !original._retried && !isAuthRoute) {
      original._retried = true;
      try {
        _refreshing = _refreshing || _doRefresh();
        const newToken = await _refreshing;
        _refreshing = null;
        if (newToken) {
          original.headers = original.headers || {};
          original.headers.Authorization = `Bearer ${newToken}`;
          return api(original);
        }
      } catch (e) {
        _refreshing = null;
        localStorage.removeItem("la_token");
        localStorage.removeItem("la_refresh");
      }
    }
    return Promise.reject(error);
  }
);

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
