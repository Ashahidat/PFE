import {
  Alert,
  Box,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Grid,
  IconButton,
  Link,
  Paper,
  Stack,
  TextField,
  Typography
} from "@mui/material";
import AddOutlinedIcon from "@mui/icons-material/AddOutlined";
import OpenInNewOutlinedIcon from "@mui/icons-material/OpenInNewOutlined";
import UploadFileOutlinedIcon from "@mui/icons-material/UploadFileOutlined";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import PageHeader from "../components/PageHeader";
import { api, ApiError } from "../lib/api";

type Project = {
  id: string;
  name: string;
  description?: string | null;
  owner_employee_id: string;
  visibility: "PUBLIC" | "DEPARTMENT";
  created_at: string;
  datasets_count: number;
  grafana_links?: any;
};

export default function ProjectsPage() {
  const navigate = useNavigate();
  const [items, setItems] = useState<Project[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [visibility, setVisibility] = useState<"PUBLIC" | "DEPARTMENT">("DEPARTMENT");
  const [createError, setCreateError] = useState<string | null>(null);
  const canCreate = useMemo(() => name.trim().length >= 2, [name]);

  async function load() {
    setError(null);
    setLoading(true);
    try {
      const res = await api.get<Project[]>("/projects/");
      setItems(res);
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

  async function createProject() {
    setCreateError(null);
    try {
      await api.post<Project>("/projects/", { name: name.trim(), description: description.trim() || null, visibility });
      setOpen(false);
      setName("");
      setDescription("");
      setVisibility("DEPARTMENT");
      await load();
    } catch (e) {
      const err = e as ApiError;
      setCreateError(err.bodyText || err.message);
    }
  }

  return (
    <Box>
      <PageHeader
        title="Projets"
        subtitle="Crée et pilote des espaces de gouvernance (visibilité, dashboards, datasets)."
        right={
          <Button variant="contained" startIcon={<AddOutlinedIcon />} onClick={() => setOpen(true)}>
            Nouveau projet
          </Button>
        }
      />
      {error ? <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert> : null}

      <Grid container spacing={2}>
        {(items || []).map((p) => (
          <Grid key={p.id} item xs={12} md={6} lg={4}>
            <Paper elevation={0} sx={{ p: 2.5, borderRadius: 3 }}>
              <Stack spacing={1}>
                <Stack direction="row" alignItems="center" justifyContent="space-between" gap={1}>
                  <Typography variant="h6" noWrap>
                    {p.name}
                  </Typography>
                  <Chip
                    size="small"
                    label={p.visibility === "PUBLIC" ? "PUBLIC" : "DEPARTMENT"}
                    color={p.visibility === "PUBLIC" ? "success" : "default"}
                    variant={p.visibility === "PUBLIC" ? "filled" : "outlined"}
                  />
                </Stack>
                <Typography variant="body2" color="text.secondary" sx={{ minHeight: 36 }}>
                  {p.description || "—"}
                </Typography>
                <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap">
                  <Chip size="small" label={`${p.datasets_count} dataset(s)`} variant="outlined" />
                  <Chip size="small" label={`Owner: ${p.owner_employee_id}`} variant="outlined" />
                </Stack>
                <Stack direction="row" spacing={1} sx={{ mt: 1 }}>
                  <Button
                    variant="outlined"
                    size="small"
                    startIcon={<UploadFileOutlinedIcon />}
                    onClick={() => navigate(`/upload?project_id=${encodeURIComponent(p.id)}`)}
                  >
                    Uploader un dataset
                  </Button>
                </Stack>
                {p.grafana_links?.folder?.url ? (
                  <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mt: 1 }}>
                    <Typography variant="caption" color="text.secondary">
                      Dashboards Grafana (read-only)
                    </Typography>
                    <IconButton size="small" component={Link} href={p.grafana_links.folder.url} target="_blank">
                      <OpenInNewOutlinedIcon fontSize="small" />
                    </IconButton>
                  </Stack>
                ) : null}
              </Stack>
            </Paper>
          </Grid>
        ))}
      </Grid>

      <Dialog open={open} onClose={() => setOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>Nouveau projet</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            {createError ? <Alert severity="error">{createError}</Alert> : null}
            <TextField label="Nom" value={name} onChange={(e) => setName(e.target.value)} autoFocus />
            <TextField
              label="Description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              multiline
              minRows={2}
            />
            <TextField
              label="Visibilité (PUBLIC ou DEPARTMENT)"
              value={visibility}
              onChange={(e) => setVisibility((e.target.value as any) || "DEPARTMENT")}
              helperText="DEPARTMENT = restreint au département ; PUBLIC = visible entreprise."
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpen(false)}>Annuler</Button>
          <Button variant="contained" onClick={createProject} disabled={!canCreate || loading}>
            Créer
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
