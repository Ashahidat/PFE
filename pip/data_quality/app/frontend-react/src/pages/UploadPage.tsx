import {
  Alert,
  Box,
  Button,
  FormControl,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Stack,
  TextField,
  Typography
} from "@mui/material";
import UploadFileOutlinedIcon from "@mui/icons-material/UploadFileOutlined";
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
    (async () => {
      try {
        const res = await api.get<any[]>("/projects/");
        const mapped = (res || []).map((p) => ({ id: p.id, name: p.name, visibility: p.visibility })) as Project[];
        setProjects(mapped);
        const q = new URLSearchParams(location.search);
        const fromProject = q.get("project_id");
        const initial = fromProject && mapped.some((p) => p.id === fromProject) ? fromProject : null;
        const pick = initial || (!projectId && mapped.length ? mapped[0].id : null);
        if (pick) onProjectChange(pick);
      } catch {
        // handled on submit/load error paths
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.search]);

  function onProjectChange(id: string) {
    setProjectId(id);
    const p = projects.find((x) => x.id === id);
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
    <Box>
      <PageHeader
        title="Upload dataset"
        subtitle="Charge un CSV, le convertit en Parquet, et initialise la gouvernance (visibilité, descriptions)."
      />
      <Paper elevation={0} sx={{ p: 3, borderRadius: 3 }}>
        <Stack spacing={2}>
          {error ? <Alert severity="error">{error}</Alert> : null}
          {success ? (
            <Alert
              severity="success"
              action={
                <Button color="inherit" size="small" onClick={() => navigate(`/describe?dataset_id=${success.dataset_id}`)}>
                  Renseigner descriptions
                </Button>
              }
            >
              Dataset uploadé. Colonnes détectées: {success.columns?.length || 0}
            </Alert>
          ) : null}

          <FormControl fullWidth>
            <InputLabel id="project-label">Projet</InputLabel>
            <Select
              labelId="project-label"
              label="Projet"
              value={projectId}
              onChange={(e) => onProjectChange(String(e.target.value))}
            >
              {projects.map((p) => (
                <MenuItem key={p.id} value={p.id}>
                  {p.name} ({p.visibility})
                </MenuItem>
              ))}
            </Select>
          </FormControl>

          <FormControl fullWidth>
            <InputLabel id="vis-label">Visibilité dataset</InputLabel>
            <Select
              labelId="vis-label"
              label="Visibilité dataset"
              value={datasetVisibility}
              onChange={(e) => setDatasetVisibility(e.target.value as any)}
            >
              <MenuItem value="DEPARTMENT">DEPARTMENT (restreint)</MenuItem>
              <MenuItem value="PUBLIC">PUBLIC (entreprise)</MenuItem>
            </Select>
          </FormControl>

          <TextField
            label="Description (optionnel)"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            multiline
            minRows={2}
          />

          <Stack direction={{ xs: "column", sm: "row" }} spacing={2} alignItems={{ sm: "center" }}>
            <Button variant="outlined" component="label" startIcon={<UploadFileOutlinedIcon />}>
              Choisir un fichier CSV
              <input hidden type="file" accept=".csv,text/csv" onChange={(e) => setFile(e.target.files?.[0] || null)} />
            </Button>
            <Typography variant="body2" color="text.secondary">
              {file ? file.name : "Aucun fichier sélectionné"}
            </Typography>
          </Stack>

          <Box>
            <Button variant="contained" onClick={submit} disabled={!canSubmit || loading}>
              Upload
            </Button>
          </Box>
        </Stack>
      </Paper>
    </Box>
  );
}
