import {
  Alert,
  Box,
  Button,
  Chip,
  LinearProgress,
  Paper,
  Stack,
  TextField,
  Typography
} from "@mui/material";
import RefreshOutlinedIcon from "@mui/icons-material/RefreshOutlined";
import PageHeader from "../components/PageHeader";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError } from "../lib/api";
import { setLastDatasetId } from "../lib/storage";

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

  async function pushAtlas(datasetId: string) {
    setError(null);
    setNotice(null);
    setLoading(true);
    try {
      await api.post(`/push-atlas/${datasetId}`, {});
      setNotice("✅ Push Atlas lancé/terminé. Rafraîchis pour voir l'état.");
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
      await api.put(`/api/datasets/${datasetId}/description`, { description: description.trim() || null });
      setNotice("Description mise à jour (DB + Atlas si synchronisé).");
      await load();
    } catch (e) {
      const err = e as ApiError;
      setError(err.bodyText || err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <Box>
      <PageHeader
        title="Mes uploads"
        subtitle="Consulte tes datasets, ouvre la gouvernance (descriptions/classifications/glossaire) et finalise vers Atlas."
        right={
          <Button startIcon={<RefreshOutlinedIcon />} onClick={load} variant="outlined" disabled={loading}>
            Rafraîchir
          </Button>
        }
      />

      {error ? <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert> : null}
      {notice ? <Alert severity="info" sx={{ mb: 2 }}>{notice}</Alert> : null}
      {loading ? <LinearProgress sx={{ mb: 2 }} /> : null}

      <Paper elevation={0} sx={{ p: 3, borderRadius: 3, mb: 2 }}>
        <TextField
          label="Filtrer (projet / dataset / id)"
          fullWidth
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        />
      </Paper>

      <Stack spacing={2}>
        {grouped.map(([projectName, list]) => (
          <Paper key={projectName} elevation={0} sx={{ p: 2.5, borderRadius: 3 }}>
            <Typography variant="subtitle1" sx={{ mb: 1 }}>
              {projectName}
            </Typography>
            <Stack spacing={1.5}>
              {list.map((d) => (
                <Paper key={d.id} variant="outlined" sx={{ p: 2 }}>
                  <Stack spacing={1}>
                    <Stack direction={{ xs: "column", sm: "row" }} spacing={1} alignItems={{ sm: "center" }}>
                      <Box sx={{ flex: 1 }}>
                        <Typography variant="body1" sx={{ fontWeight: 600 }}>
                          {d.name}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          {d.id} {d.created_at ? `· ${d.created_at}` : ""}
                        </Typography>
                      </Box>
                      <Stack direction="row" spacing={1} flexWrap="wrap">
                        <Chip size="small" label={`Visibilité: ${d.classification}`} />
                        <Chip size="small" label={`${d.columns_count} colonnes`} variant="outlined" />
                        <Chip
                          size="small"
                          label={d.atlas_synced ? "Atlas: synced" : "Atlas: not synced"}
                          color={d.atlas_synced ? "success" : "warning"}
                          variant={d.atlas_synced ? "filled" : "outlined"}
                        />
                      </Stack>
                    </Stack>

                    <Stack direction={{ xs: "column", md: "row" }} spacing={1} alignItems={{ md: "center" }}>
                      <Button
                        variant="outlined"
                        onClick={() => {
                          setLastDatasetId(d.id);
                          navigate(`/describe?dataset_id=${encodeURIComponent(d.id)}`);
                        }}
                      >
                        Ouvrir gouvernance
                      </Button>
                      <Button
                        variant="outlined"
                        onClick={() => {
                          setLastDatasetId(d.id);
                          navigate("/run");
                        }}
                      >
                        Valider qualité (Airflow)
                      </Button>
                      <Button
                        variant="contained"
                        onClick={() => pushAtlas(d.id)}
                        disabled={loading}
                        title={!d.atlas_guid ? "1ère synchro Atlas (push) crée le guid" : undefined}
                      >
                        Finaliser (push Atlas)
                      </Button>
                    </Stack>

                    <Typography variant="subtitle2" sx={{ mt: 1 }}>
                      Description dataset (édition directe = synchro immédiate si Atlas sync)
                    </Typography>
                    <Stack direction={{ xs: "column", md: "row" }} spacing={1} alignItems={{ md: "center" }}>
                      <TextField
                        fullWidth
                        size="small"
                        placeholder="Description…"
                        value={descDraft[d.id] ?? ""}
                        onChange={(e) => setDescDraft((prev) => ({ ...prev, [d.id]: e.target.value }))}
                        disabled={!d.can_edit}
                        helperText={!d.can_edit ? "Pour éditer directement ici: dataset doit être Atlas synced + droits." : " "}
                      />
                      <Button
                        variant="outlined"
                        disabled={!d.can_edit || loading}
                        onClick={() => void saveDescription(d.id, descDraft[d.id] ?? "")}
                      >
                        Sauver
                      </Button>
                    </Stack>
                  </Stack>
                </Paper>
              ))}
            </Stack>
          </Paper>
        ))}
        {items.length === 0 && !loading ? (
          <Alert severity="info">Aucun dataset visible. Uploade un dataset puis reviens ici.</Alert>
        ) : null}
      </Stack>
    </Box>
  );
}
