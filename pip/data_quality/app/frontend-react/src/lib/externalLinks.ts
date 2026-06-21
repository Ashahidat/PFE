import { getUserRole } from "./storage";

const viteEnv = (typeof import.meta !== "undefined" && (import.meta as any).env) ? (import.meta as any).env : {};

function getWindowLocation() {
  if (typeof window === "undefined") return null;
  return window.location;
}

function defaultAtlasUiUrl() {
  const location = getWindowLocation();
  if (!location) return "http://localhost:21001/n/index.html";
  return `${location.protocol}//${location.hostname}:21001/n/index.html`;
}

function defaultGrafanaUrl() {
  // Use the backend as the single browser entrypoint for Grafana.
  // This avoids inheriting a stale origin such as :8081 from the current page.
  return "http://localhost:8000/api/grafana/dashboards";
}

export const ATLAS_UI_URL = viteEnv.VITE_ATLAS_UI_URL || defaultAtlasUiUrl();
export const GRAFANA_DASHBOARDS_URL = viteEnv.VITE_GRAFANA_DASHBOARDS_URL || defaultGrafanaUrl();

export function toGrafanaBackendHref(href: string | null | undefined): string | null {
  if (!href) return null;
  try {
    const url = new URL(href, "http://localhost:8000");
    if (url.pathname.startsWith("/api/grafana/")) {
      return url.toString();
    }
    return href;
  } catch {
    return href;
  }
}

const ATLAS_ALLOWED_ROLES = new Set(["SUPER_ADMIN", "ADMIN", "ADMIN_GLOSSAIRE", "AUDIT"]);

export function canOpenAtlasUi(role: string | null = getUserRole()): boolean {
  return role !== null && ATLAS_ALLOWED_ROLES.has(role);
}
