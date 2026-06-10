import { getUserRole } from "./storage";

export const ATLAS_UI_URL = import.meta.env.VITE_ATLAS_UI_URL || "http://localhost:21001/n/index.html#!/search";

const ATLAS_ALLOWED_ROLES = new Set(["SUPER_ADMIN", "ADMIN", "ADMIN_GLOSSAIRE", "AUDIT"]);

export function canOpenAtlasUi(role: string | null = getUserRole()): boolean {
  return role !== null && ATLAS_ALLOWED_ROLES.has(role);
}
