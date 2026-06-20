import { getUserRole } from "./storage";

const viteEnv = (typeof import.meta !== "undefined" && (import.meta as any).env) ? (import.meta as any).env : {};

function getWindowLocation() {
  if (typeof window === "undefined") return null;
  return window.location;
}

function defaultAtlasUiUrl() {
  const location = getWindowLocation();
  if (!location) return "http://localhost:21001/login.jsp";
  return `${location.protocol}//${location.hostname}:21001/login.jsp`;
}

function defaultGrafanaUrl() {
  const location = getWindowLocation();
  if (!location) return "http://localhost:8081/api/grafana/";
  return `${location.protocol}//${location.hostname}:8081/api/grafana/`;
}

export const ATLAS_UI_URL = viteEnv.VITE_ATLAS_UI_URL || defaultAtlasUiUrl();
export const GRAFANA_DASHBOARDS_URL = viteEnv.VITE_GRAFANA_DASHBOARDS_URL || defaultGrafanaUrl();

const ATLAS_ALLOWED_ROLES = new Set(["SUPER_ADMIN", "ADMIN", "ADMIN_GLOSSAIRE", "AUDIT"]);

export function canOpenAtlasUi(role: string | null = getUserRole()): boolean {
  return role !== null && ATLAS_ALLOWED_ROLES.has(role);
}
