// Centralized API base URL resolution.
// Priority:
// 1) window.API_URL if set (e.g., injected config)
// 2) ?api=https://host:port query param
// 3) Same-origin when served by backend (recommended: http://localhost:8000/app/login)
// 4) Local dev fallback: http(s)://<hostname>:8000 for localhost / 127.0.0.1
(() => {
  if (window.API_URL) return;

  try {
    const url = new URL(window.location.href);
    const apiParam = url.searchParams.get("api");
    if (apiParam) {
      window.API_URL = apiParam.replace(/\/+$/, "");
      return;
    }

    const { protocol, hostname, port, origin } = window.location;
    if (port === "8000") {
      window.API_URL = origin;
      return;
    }

    if (hostname === "localhost" || hostname === "127.0.0.1") {
      window.API_URL = `${protocol}//${hostname}:8000`;
      return;
    }

    window.API_URL = origin;
  } catch {
    window.API_URL = window.location.origin;
  }
})();
