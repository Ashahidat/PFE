import { useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import PageHeader from "../components/PageHeader";
import { api, ApiError } from "../lib/api";
import { setLastDatasetId } from "../lib/storage";

type Project = { id: string; name: string; visibility: "PUBLIC" | "DEPARTMENT" };

type UploadResponse = {
  dataset_id: string;
  project_id: string;
  columns: string[];
  hash: string;
  dataset_visibility: "PUBLIC" | "DEPARTMENT";
};

export default function UploadPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState<string>("");
  const [description, setDescription] = useState("");
  const [datasetVisibility, setDatasetVisibility] = useState<"PUBLIC" | "DEPARTMENT">("DEPARTMENT");
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<UploadResponse | null>(null);

  const canSubmit = useMemo(() => Boolean(file && projectId), [file, projectId]);

  useEffect(() => {
    if (!success?.dataset_id) return;
    const timer = window.setTimeout(() => {
      navigate(`/describe?dataset_id=${encodeURIComponent(success.dataset_id)}`);
    }, 1200);
    return () => window.clearTimeout(timer);
  }, [navigate, success?.dataset_id]);

  useEffect(() => {
    (async () => {
      try {
        const res = await api.get<any[]>("/projects/");
        const mapped = (res || []).map((p) => ({ id: p.id, name: p.name, visibility: p.visibility })) as Project[];
        setProjects(mapped);
        const q = new URLSearchParams(location.search);
        const fromProject = q.get("project_id");
        const initial = fromProject && mapped.some((p) => p.id === fromProject) ? fromProject : null;
        const pick = initial || (!projectId && mapped.length ? mapped[0].id : null);
        if (pick) onProjectChange(pick, mapped);
      } catch {
        // handled on submit/load error paths
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.search]);

  function onProjectChange(id: string, list: Project[] = projects) {
    setProjectId(id);
    const p = list.find((x) => x.id === id);
    if (p) setDatasetVisibility(p.visibility || "DEPARTMENT");
  }

  async function submit() {
    if (!file || !projectId) return;
    setError(null);
    setSuccess(null);
    setLoading(true);
    try {
      const form = new FormData();
      form.append("file", file);
      form.append("project_id", projectId);
      if (description.trim()) form.append("description", description.trim());
      form.append("dataset_visibility", datasetVisibility);
      const res = await api.postForm<UploadResponse>("/upload", form);
      setSuccess(res);
      setLastDatasetId(res.dataset_id);
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
        title="Upload dataset"
        subtitle="Charge un CSV, initialise la gouvernance, puis passe automatiquement à l’étape suivante."
      />

      <section
        style={{
          borderRadius: 24,
          padding: 20,
          marginBottom: 16,
          background: "linear-gradient(135deg, rgba(30,64,175,0.08), rgba(15,118,110,0.08))",
          border: "1px solid rgba(148,163,184,0.25)"
        }}
      >
        <div style={{ fontSize: 18, fontWeight: 700, color: "#0f172a", marginBottom: 8 }}>Parcours recommandé</div>
        <div style={{ fontSize: 14, lineHeight: 1.7, color: "#475569" }}>
          1. Choisis le projet et la visibilité du dataset. 2. Upload. 3. L’application t’envoie automatiquement vers
          les descriptions. 4. Puis la qualité et Atlas.
        </div>
      </section>

      <section
        style={{
          borderRadius: 24,
          padding: 24,
          background: "#fff",
          border: "1px solid #e5e7eb",
          boxShadow: "0 10px 30px rgba(15,23,42,0.05)"
        }}
      >
        <div style={{ display: "grid", gap: 16 }}>
          {error ? (
            <div
              style={{
                borderRadius: 12,
                padding: 12,
                background: "#fef2f2",
                color: "#991b1b",
                border: "1px solid #fecaca"
              }}
            >
              {error}
            </div>
          ) : null}

          {success ? (
            <div
              style={{
                borderRadius: 12,
                padding: 12,
                background: "#ecfdf5",
                color: "#065f46",
                border: "1px solid #a7f3d0"
              }}
            >
              Dataset uploadé. Colonnes détectées: {success.columns?.length || 0}. Redirection vers les descriptions en
              cours.
              <div style={{ marginTop: 10 }}>
                <button
                  type="button"
                  onClick={() => navigate(`/describe?dataset_id=${encodeURIComponent(success.dataset_id)}`)}
                  style={{
                    border: "none",
                    borderRadius: 10,
                    padding: "10px 14px",
                    background: "#065f46",
                    color: "#fff",
                    fontWeight: 700,
                    cursor: "pointer"
                  }}
                >
                  Renseigner descriptions
                </button>
              </div>
            </div>
          ) : null}

          <label style={{ display: "grid", gap: 8 }}>
            <span style={{ fontSize: 14, fontWeight: 700, color: "#0f172a" }}>Projet</span>
            <select
              value={projectId}
              onChange={(e) => onProjectChange(e.target.value)}
              style={{
                borderRadius: 12,
                border: "1px solid #cbd5e1",
                padding: "12px 14px",
                fontSize: 14,
                background: "#fff"
              }}
            >
              <option value="">Choisir un projet</option>
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} ({p.visibility})
                </option>
              ))}
            </select>
          </label>

          <label style={{ display: "grid", gap: 8 }}>
            <span style={{ fontSize: 14, fontWeight: 700, color: "#0f172a" }}>Visibilité dataset</span>
            <select
              value={datasetVisibility}
              onChange={(e) => setDatasetVisibility(e.target.value as "PUBLIC" | "DEPARTMENT")}
              style={{
                borderRadius: 12,
                border: "1px solid #cbd5e1",
                padding: "12px 14px",
                fontSize: 14,
                background: "#fff"
              }}
            >
              <option value="DEPARTMENT">DEPARTMENT (restreint)</option>
              <option value="PUBLIC">PUBLIC (entreprise)</option>
            </select>
          </label>

          <div style={{ fontSize: 12, color: "#64748b", lineHeight: 1.6 }}>
            Cette visibilité détermine qui pourra voir le dataset dans l’application et quelle classification sera
            poussée vers Atlas.
          </div>

          <label style={{ display: "grid", gap: 8 }}>
            <span style={{ fontSize: 14, fontWeight: 700, color: "#0f172a" }}>Description (optionnel)</span>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              style={{
                borderRadius: 12,
                border: "1px solid #cbd5e1",
                padding: "12px 14px",
                fontSize: 14,
                fontFamily: "inherit",
                resize: "vertical"
              }}
            />
          </label>

          <label style={{ display: "grid", gap: 8 }}>
            <span style={{ fontSize: 14, fontWeight: 700, color: "#0f172a" }}>Fichier CSV</span>
            <input
              type="file"
              accept=".csv,text/csv"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
              style={{ fontSize: 14 }}
            />
          </label>
          <div style={{ fontSize: 13, color: "#64748b" }}>{file ? file.name : "Aucun fichier sélectionné"}</div>

          <div>
            <button
              type="button"
              onClick={submit}
              disabled={!canSubmit || loading}
              style={{
                border: "none",
                borderRadius: 12,
                padding: "12px 16px",
                background: !canSubmit || loading ? "#94a3b8" : "#1e40af",
                color: "#fff",
                fontWeight: 700,
                cursor: !canSubmit || loading ? "not-allowed" : "pointer"
              }}
            >
              {loading ? "Upload en cours..." : "Upload"}
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}
