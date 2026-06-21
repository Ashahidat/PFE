import { Outlet, useLocation, useNavigate } from "react-router-dom";
import { clearToken, getUserRole } from "../lib/storage";
import { ATLAS_UI_URL, GRAFANA_DASHBOARDS_URL, canOpenAtlasUi } from "../lib/externalLinks";

type NavItem = { to?: string; label: string; href?: string };
type NavGroup = { title: string; items: NavItem[] };

function buildNav(role: string | null): NavGroup[] {
  const canUpload = role && role !== "AUDIT";
  const canManageGlossary = role && ["ADMIN", "ADMIN_GLOSSAIRE", "SUPER_ADMIN"].includes(role);
  const canManageUsers = role && ["ADMIN", "ADMIN_GLOSSAIRE", "SUPER_ADMIN"].includes(role);
  const canManageDepartments = role === "SUPER_ADMIN";

  const workflowItems: NavItem[] = [];
  if (canUpload) {
    workflowItems.push({ to: "/uploads", label: "Mes datasets" });
    workflowItems.push({ to: "/upload", label: "Importer un dataset" });
    workflowItems.push({ to: "/describe", label: "Décrire et classer" });
    workflowItems.push({ to: "/run", label: "Lancer la qualité" });
  }
  workflowItems.push({ to: "/results", label: "Voir les résultats" });

  const adminItems: NavItem[] = [];
  if (canManageGlossary) adminItems.push({ to: "/glossary", label: "Glossaire" });
  if (canManageUsers) adminItems.push({ to: "/users", label: "Utilisateurs" });
  if (canManageDepartments) adminItems.push({ to: "/departments", label: "Départements" });

  return [
    {
      title: "Démarrage",
      items: [
        { to: "/home", label: "Accueil" },
        { to: "/projects", label: "Projets" },
        ...(canOpenAtlasUi(role) ? [{ href: ATLAS_UI_URL, label: "Atlas BETA UI" }] : []),
        { href: GRAFANA_DASHBOARDS_URL, label: "Dashboards Grafana (read-only)" }
      ]
    },
    ...(workflowItems.length ? [{ title: "Parcours data", items: workflowItems }] : []),
    ...(adminItems.length ? [{ title: "Administration", items: adminItems }] : []),
    {
      title: "Compte",
      items: [{ to: "/profile", label: "Mon profil" }]
    }
  ];
}

export default function Shell() {
  const location = useLocation();
  const navigate = useNavigate();
  const role = getUserRole();
  const nav = buildNav(role);

  return (
    <div style={{ display: "flex", minHeight: "100vh", background: "#f6f7fb", color: "#111827" }}>
      <aside
        style={{
          width: 280,
          background: "#ffffff",
          borderRight: "1px solid #e5e7eb",
          padding: "20px 16px",
          boxSizing: "border-box",
          position: "sticky",
          top: 0,
          height: "100vh",
          overflow: "auto"
        }}
      >
        <div style={{ marginBottom: 16 }}>
          <div style={{ fontSize: 12, color: "#6b7280", textTransform: "uppercase", letterSpacing: 0.08 }}>
            Commence ici
          </div>
          <div style={{ marginTop: 6, fontSize: 14, color: "#4b5563" }}>
            Le menu suit le parcours recommandé pour éviter de se perdre.
          </div>
        </div>

        {nav.map((group) => (
          <section key={group.title} style={{ marginBottom: 20 }}>
            <div style={{ fontSize: 12, color: "#6b7280", textTransform: "uppercase", letterSpacing: 0.08, margin: "10px 0" }}>
              {group.title}
            </div>
            <div style={{ display: "grid", gap: 6 }}>
              {group.items.map((item) => {
                const active = item.to ? (location.pathname === item.to || location.pathname.startsWith(item.to + "/")) : false;
                const sharedStyle = {
                  width: "100%",
                  textAlign: "left" as const,
                  border: "1px solid " + (active ? "#1e40af" : "#e5e7eb"),
                  background: active ? "rgba(30,64,175,0.08)" : "#fff",
                  color: "#111827",
                  borderRadius: 10,
                  padding: "10px 12px",
                  cursor: "pointer",
                  fontSize: 14,
                  fontWeight: active ? 700 : 500,
                  textDecoration: "none"
                };
                if (item.href) {
                  return (
                    <a
                      key={item.label}
                      href={item.href}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={sharedStyle}
                    >
                      {item.label}
                    </a>
                  );
                }
                return (
                  <button
                    key={item.to}
                    type="button"
                    onClick={() => navigate(item.to ?? "/home")}
                    style={sharedStyle}
                  >
                    {item.label}
                  </button>
                );
              })}
            </div>
          </section>
        ))}

        <button
          type="button"
          onClick={() => {
            clearToken();
            navigate("/login");
          }}
          style={{
            width: "100%",
            marginTop: 16,
            border: "1px solid #d1d5db",
            borderRadius: 10,
            background: "#fff",
            padding: "10px 12px",
            cursor: "pointer"
          }}
        >
          Se déconnecter
        </button>
      </aside>

      <main style={{ flex: 1, padding: 24 }}>
        <Outlet />
      </main>
    </div>
  );
}
