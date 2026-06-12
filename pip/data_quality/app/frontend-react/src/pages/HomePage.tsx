import { useNavigate } from "react-router-dom";
import PageHeader from "../components/PageHeader";
import { getLastDatasetId, getUserRole } from "../lib/storage";

type HomeAction = {
  title: string;
  description: string;
  actionLabel: string;
  to: string;
  tone?: "primary" | "muted";
};

function ActionTile({ title, description, actionLabel, to, tone = "muted", navigate }: HomeAction & { navigate: (to: string) => void }) {
  return (
    <button
      type="button"
      onClick={() => navigate(to)}
      style={{
        width: "100%",
        textAlign: "left",
        borderRadius: 18,
        border: tone === "primary" ? "1px solid rgba(30,64,175,0.24)" : "1px solid #e5e7eb",
        background:
          tone === "primary"
            ? "linear-gradient(180deg, rgba(30,64,175,0.08), rgba(15,118,110,0.05))"
            : "#fff",
        boxShadow: "0 10px 30px rgba(15,23,42,0.06)",
        padding: 20,
        cursor: "pointer"
      }}
    >
      <div style={{ fontSize: 12, letterSpacing: 0.08, textTransform: "uppercase", color: "#6b7280", marginBottom: 8 }}>
        {actionLabel}
      </div>
      <div style={{ fontSize: 18, fontWeight: 700, color: "#111827", marginBottom: 8 }}>{title}</div>
      <div style={{ fontSize: 14, lineHeight: 1.6, color: "#4b5563" }}>{description}</div>
    </button>
  );
}

export default function HomePage() {
  const navigate = useNavigate();
  const role = getUserRole();
  const lastDatasetId = getLastDatasetId();
  const isSuperAdmin = role === "SUPER_ADMIN";
  const canManageAdmins = role && ["ADMIN", "ADMIN_GLOSSAIRE", "SUPER_ADMIN"].includes(role);
  const canWorkOnData = role && role !== "AUDIT";

  const dataActions: HomeAction[] = [
    {
      title: "Importer un dataset",
      description: "Charge un fichier CSV. Une fois l'import terminé, on vous envoie directement vers la suite.",
      actionLabel: "Commencer",
      to: "/upload",
      tone: "primary"
    },
    {
      title: "Mes datasets",
      description: "Retrouve les datasets, leur progression et l'étape recommandée pour chacun.",
      actionLabel: "Ouvrir",
      to: "/uploads"
    },
    {
      title: "Décrire et classer",
      description: "Complète les descriptions, les classifications de colonnes et le glossaire.",
      actionLabel: "Continuer",
      to: "/describe"
    },
    {
      title: "Lancer la qualité",
      description: "Déclenche les contrôles automatiques avant la synchronisation Atlas.",
      actionLabel: "Valider",
      to: "/run"
    },
    {
      title: "Voir les résultats",
      description: "Lis les contrôles, puis finalise la synchronisation vers Atlas si tout est prêt.",
      actionLabel: "Voir",
      to: "/results"
    },
    {
      title: "Projets",
      description: "Visualise les espaces de gouvernance et ouvre l’accès aux datasets associés.",
      actionLabel: "Explorer",
      to: "/projects"
    }
  ];

  const adminActions: HomeAction[] = [
    {
      title: "Utilisateurs",
      description: "Crée et ajuste les comptes, les rôles et les départements.",
      actionLabel: "Gérer",
      to: "/users"
    },
    {
      title: "Glossaire",
      description: "Pilote les termes métiers et leurs affectations.",
      actionLabel: "Gérer",
      to: "/glossary"
    }
  ];

  const superAdminActions: HomeAction[] = [
    {
      title: "Départements",
      description: "Crée les départements et gère les périmètres d’administration.",
      actionLabel: "Configurer",
      to: "/departments"
    }
  ];

  return (
    <div>
      <PageHeader
        title="Accueil"
        subtitle="Un point d’entrée simple qui explique quoi faire, dans quel ordre, et pourquoi."
      />

      <section
        style={{
          borderRadius: 24,
          padding: 24,
          marginBottom: 24,
          background: "linear-gradient(135deg, rgba(30,64,175,0.10), rgba(15,118,110,0.10))",
          border: "1px solid rgba(148,163,184,0.25)"
        }}
      >
        <div style={{ display: "grid", gap: 16 }}>
          <div>
            <div style={{ fontSize: 26, fontWeight: 800, color: "#0f172a", marginBottom: 8 }}>
              Bienvenue dans votre espace de gouvernance
            </div>
            <div style={{ fontSize: 15, lineHeight: 1.7, color: "#475569", maxWidth: 900 }}>
              Atlas sert de catalogue technique. L’application vous guide pour que chaque étape soit claire et qu’il
              n’y ait pas besoin de deviner où cliquer ensuite.
            </div>
          </div>

          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {[
              "Atlas = catalogue technique",
              "PUBLIC = visible à l'entreprise",
              "DEPARTMENT = visible au département",
              "PII / SENSITIVE = classification des colonnes"
            ].map((label) => (
              <span
                key={label}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  borderRadius: 999,
                  border: "1px solid rgba(148,163,184,0.35)",
                  padding: "8px 12px",
                  background: "rgba(255,255,255,0.72)",
                  fontSize: 13,
                  color: "#334155"
                }}
              >
                {label}
              </span>
            ))}
          </div>

          {lastDatasetId ? (
            <div style={{ display: "flex", flexWrap: "wrap", gap: 10 }}>
              <button
                type="button"
                onClick={() => navigate(`/describe?dataset_id=${encodeURIComponent(lastDatasetId)}`)}
                style={{
                  border: "none",
                  borderRadius: 12,
                  padding: "12px 16px",
                  background: "#1e40af",
                  color: "#fff",
                  fontWeight: 700,
                  cursor: "pointer"
                }}
              >
                Reprendre le dernier dataset
              </button>
              <button
                type="button"
                onClick={() => navigate("/uploads")}
                style={{
                  border: "1px solid #cbd5e1",
                  borderRadius: 12,
                  padding: "12px 16px",
                  background: "#fff",
                  color: "#0f172a",
                  fontWeight: 700,
                  cursor: "pointer"
                }}
              >
                Voir mes datasets
              </button>
            </div>
          ) : null}
        </div>
      </section>

      <div
        style={{
          display: "grid",
          gap: 16,
          gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))"
        }}
      >
        {canWorkOnData
          ? dataActions.map((action) => (
              <ActionTile key={action.to} {...action} navigate={navigate} />
            ))
          : null}

        {canManageAdmins ? adminActions.map((action) => <ActionTile key={action.to} {...action} navigate={navigate} />) : null}

        {isSuperAdmin ? superAdminActions.map((action) => <ActionTile key={action.to} {...action} navigate={navigate} />) : null}
      </div>
    </div>
  );
}
