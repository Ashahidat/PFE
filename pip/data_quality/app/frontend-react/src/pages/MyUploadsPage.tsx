import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import PageHeader from "../components/PageHeader";
import { ATLAS_UI_URL, canOpenAtlasUi } from "../lib/externalLinks";
import { api, ApiError } from "../lib/api";
import { getUserRole, setLastDatasetId } from "../lib/storage";

type DatasetItem = {
  id: string;
  name: string;
  classification: string;
  columns_count: number;
  atlas_synced: boolean;
  atlas_guid?: string | null;
  can_edit: boolean;
  description?: string | null;
  created_at?: string | null;
  project?: { id: string; name: string; visibility: string } | null;
};

export default function MyUploadsPage() {
  const navigate = useNavigate();
  const [items, setItems] = useState<DatasetItem[]>([]);
  const [descDraft, setDescDraft] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [filter, setFilter] = useState("");

  async function load() {
    setError(null);
    setNotice(null);
    setLoading(true);
    try {
      const res = await api.get<DatasetItem[]>("/api/datasets/my-uploads");
      setItems(res || []);
      const next: Record<string, string> = {};
      for (const d of res || []) next[d.id] = d.description || "";
      setDescDraft(next);
    } catch (e) {
      const err = e as ApiError;
      setError(err.bodyText || err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  const grouped = useMemo(() => {
    const q = filter.trim().toLowerCase();
    const list = (items || []).filter((d) => {
      if (!q) return true;
      return (
        String(d.name || "").toLowerCase().includes(q) ||
        String(d.project?.name || "").toLowerCase().includes(q) ||
        String(d.id || "").toLowerCase().includes(q)
      );
    });
    const map = new Map<string, DatasetItem[]>();
    for (const d of list) {
      const key = d.project?.name || "Sans projet";
      map.set(key, [...(map.get(key) || []), d]);
    }
    return Array.from(map.entries()).sort((a, b) => a[0].localeCompare(b[0]));
  }, [items, filter]);

  function getNextStep(d: DatasetItem) {
    if (!String(d.description || "").trim()) {
      return { label: "Renseigner la gouvernance", to: `/describe?dataset_id=${encodeURIComponent(d.id)}` };
    }
    if (!d.atlas_synced) {
      return { label: "Passer à la qualité", to: "/run" };
    }
    return { label: "Dataset finalisé", to: `/describe?dataset_id=${encodeURIComponent(d.id)}` };
  }

  async function pushAtlas(datasetId: string) {
    setError(null);
    setNotice(null);
    setLoading(true);
    try {
      await api.post(`/push-atlas/${datasetId}`, {});
      setNotice("Push Atlas lancé/terminé. Rafraîchis pour voir l'état.");
      await load();
    } catch (e) {
      const err = e as ApiError;
      setError(err.bodyText || err.message);
    } finally {
      setLoading(false);
    }
  }

  async function saveDescription(datasetId: string, description: string) {
    setError(null);
    setNotice(null);
    setLoading(true);
    try {
      const res = await api.put<{ pending_atlas_sync?: boolean }>(`/api/datasets/${datasetId}/description`, {
        description: description.trim() || null
      });
      setNotice(
        res?.pending_atlas_sync
          ? "Description mise à jour en base. Atlas sera synchronisé au prochain push."
          : "Description mise à jour (DB + Atlas)."
      );
      await load();
    } catch (e) {
      const err = e as ApiError;
      setError(err.bodyText || err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <PageHeader
        title="Mes uploads"
        subtitle="Consulte tes datasets, ouvre la gouvernance et finalise vers Atlas sans te perdre."
        right={
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
            {canOpenAtlasUi(getUserRole()) ? (
              <a
                href={ATLAS_UI_URL}
                target="_blank"
                rel="noopener noreferrer"
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  border: "1px solid #cbd5e1",
                  borderRadius: 12,
                  padding: "10px 14px",
                  color: "#0f172a",
                  textDecoration: "none",
                  fontWeight: 700,
                  background: "#fff"
                }}
              >
                Consulter le catalogue
              </a>
            ) : null}
            <button
              type="button"
              onClick={load}
              disabled={loading}
              style={{
                border: "1px solid #cbd5e1",
                borderRadius: 12,
                padding: "10px 14px",
                color: "#0f172a",
                background: "#fff",
                fontWeight: 700,
                cursor: "pointer"
              }}
            >
              Rafraîchir
            </button>
          </div>
        }
      />

      <section
        style={{
          borderRadius: 24,
          padding: 20,
          marginBottom: 16,
          background: "linear-gradient(135deg, rgba(15,118,110,0.08), rgba(30,64,175,0.08))",
          border: "1px solid rgba(148,163,184,0.25)"
        }}
      >
        <div style={{ fontSize: 18, fontWeight: 700, color: "#0f172a", marginBottom: 8 }}>
          Ce que vous devez faire ensuite
        </div>
        <div style={{ fontSize: 14, lineHeight: 1.7, color: "#475569" }}>
          Chaque dataset indique sa prochaine étape recommandée pour éviter les allers-retours inutiles.
        </div>
      </section>

      {error ? (
        <div
          style={{
            borderRadius: 12,
            padding: 12,
            marginBottom: 16,
            background: "#fef2f2",
            color: "#991b1b",
            border: "1px solid #fecaca"
          }}
        >
          {error}
        </div>
      ) : null}

      {notice ? (
        <div
          style={{
            borderRadius: 12,
            padding: 12,
            marginBottom: 16,
            background: "#eff6ff",
            color: "#1d4ed8",
            border: "1px solid #bfdbfe"
          }}
        >
          {notice}
        </div>
      ) : null}

      {loading ? (
        <div style={{ height: 4, borderRadius: 999, background: "linear-gradient(90deg, #1e40af, #0f766e)", marginBottom: 16 }} />
      ) : null}

      <section
        style={{
          borderRadius: 24,
          padding: 20,
          marginBottom: 16,
          background: "#fff",
          border: "1px solid #e5e7eb"
        }}
      >
        <label style={{ display: "grid", gap: 8 }}>
          <span style={{ fontSize: 14, fontWeight: 700, color: "#0f172a" }}>Filtrer (projet / dataset / id)</span>
          <input
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            style={{
              borderRadius: 12,
              border: "1px solid #cbd5e1",
              padding: "12px 14px",
              fontSize: 14
            }}
          />
        </label>
      </section>

      <div style={{ display: "grid", gap: 16 }}>
        {grouped.map(([projectName, list]) => (
          <section
            key={projectName}
            style={{
              borderRadius: 24,
              padding: 20,
              background: "#fff",
              border: "1px solid #e5e7eb"
            }}
          >
            <div style={{ fontSize: 18, fontWeight: 700, color: "#0f172a", marginBottom: 12 }}>{projectName}</div>

            <div style={{ display: "grid", gap: 12 }}>
              {list.map((d) => {
                const currentValue = descDraft[d.id] ?? "";
                const savedValue = d.description ?? "";
                const isDirty = currentValue !== savedValue;

                return (
                  <article
                    key={d.id}
                    style={{
                      borderRadius: 18,
                      border: "1px solid #e5e7eb",
                      padding: 16,
                      background: "#fff"
                    }}
                  >
                    <div style={{ display: "grid", gap: 12 }}>
                      <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
                        <div style={{ minWidth: 0 }}>
                          <div style={{ fontSize: 16, fontWeight: 700, color: "#0f172a" }}>{d.name}</div>
                          <div style={{ fontSize: 12, color: "#64748b", marginTop: 4 }}>
                            {d.id} {d.created_at ? `· ${d.created_at}` : ""}
                          </div>
                        </div>
                        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                          <span style={chipStyle}>{`Visibilité: ${d.classification}`}</span>
                          <span style={chipStyle}>{`${d.columns_count} colonnes`}</span>
                          <span style={chipStyle}>{d.atlas_synced ? "Atlas: synced" : "Atlas: not synced"}</span>
                        </div>
                      </div>

                      <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
                        <button
                          type="button"
                          onClick={() => {
                            const next = getNextStep(d);
                            setLastDatasetId(d.id);
                            navigate(next.to);
                          }}
                          style={primaryButton}
                        >
                          {getNextStep(d).label}
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            setLastDatasetId(d.id);
                            navigate(`/describe?dataset_id=${encodeURIComponent(d.id)}`);
                          }}
                          style={secondaryButton}
                        >
                          Ouvrir gouvernance
                        </button>
                        <button
                          type="button"
                          onClick={() => pushAtlas(d.id)}
                          disabled={loading}
                          style={{
                            ...secondaryButton,
                            opacity: loading ? 0.6 : 1,
                            cursor: loading ? "not-allowed" : "pointer"
                          }}
                          title={
                            !d.atlas_guid
                              ? "1ère synchro Atlas (push) crée le guid"
                              : "Relance une synchronisation Atlas pour créer une nouvelle version"
                          }
                        >
                          Finaliser Atlas
                        </button>
                      </div>

                      <div style={{ fontSize: 14, fontWeight: 700, color: "#0f172a", marginTop: 4 }}>
                        Description dataset (éditable par le propriétaire)
                      </div>
                      <div style={{ display: "grid", gap: 10 }}>
                        <textarea
                          value={currentValue}
                          onChange={(e) => setDescDraft((prev) => ({ ...prev, [d.id]: e.target.value }))}
                          disabled={!d.can_edit}
                          rows={3}
                          placeholder="Description…"
                          style={{
                            borderRadius: 12,
                            border: "1px solid #cbd5e1",
                            padding: "12px 14px",
                            fontSize: 14,
                            fontFamily: "inherit",
                            resize: "vertical"
                          }}
                        />
                        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
                          <button
                            type="button"
                            onClick={() => saveDescription(d.id, currentValue)}
                            disabled={!d.can_edit || !isDirty || loading}
                            style={{
                              ...primaryButton,
                              opacity: !d.can_edit || !isDirty || loading ? 0.6 : 1,
                              cursor: !d.can_edit || !isDirty || loading ? "not-allowed" : "pointer"
                            }}
                          >
                            Sauvegarder
                          </button>
                          {!d.can_edit ? (
                            <span style={{ fontSize: 13, color: "#64748b", alignSelf: "center" }}>
                              Vous n'avez pas les droits pour modifier ce dataset.
                            </span>
                          ) : null}
                        </div>
                      </div>
                    </div>
                  </article>
                );
              })}
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}

const chipStyle: React.CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  borderRadius: 999,
  padding: "6px 10px",
  background: "#f8fafc",
  border: "1px solid #e2e8f0",
  color: "#334155",
  fontSize: 12,
  fontWeight: 600
};

const primaryButton: React.CSSProperties = {
  border: "none",
  borderRadius: 12,
  padding: "12px 14px",
  background: "#1e40af",
  color: "#fff",
  fontWeight: 700
};

const secondaryButton: React.CSSProperties = {
  border: "1px solid #cbd5e1",
  borderRadius: 12,
  padding: "12px 14px",
  background: "#fff",
  color: "#0f172a",
  fontWeight: 700
};
