import {
  Alert,
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  Paper,
  Stack,
  Switch,
  TextField,
  Typography
} from "@mui/material";
import AddOutlinedIcon from "@mui/icons-material/AddOutlined";
import EditOutlinedIcon from "@mui/icons-material/EditOutlined";
import BusinessOutlinedIcon from "@mui/icons-material/BusinessOutlined";
import PageHeader from "../components/PageHeader";
import { useEffect, useMemo, useState } from "react";
import { api, ApiError } from "../lib/api";

type Department = { code: string; label: string; is_active: boolean };

export default function DepartmentsAdminPage() {
  const [items, setItems] = useState<Department[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  // Create form
  const [code, setCode] = useState("");
  const [label, setLabel] = useState("");
  const [isActive, setIsActive] = useState(true);
  const canCreate = useMemo(() => code.trim() && label.trim(), [code, label]);

  // Edit dialog
  const [editOpen, setEditOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<Department | null>(null);
  const [editLabel, setEditLabel] = useState("");
  const [editIsActive, setEditIsActive] = useState(true);

  async function loadAll() {
    setError(null);
    setNotice(null);
    setLoading(true);
    try {
      const depts = await api.get<Department[]>("/departments?include_inactive=true");
      setItems(depts || []);
    } catch (e) {
      const err = e as ApiError;
      setError(err.bodyText || err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadAll();
  }, []);

  async function createDepartment() {
    if (!canCreate) return;
    setError(null);
    setNotice(null);
    setLoading(true);
    try {
      await api.post<Department>("/departments", {
        code: code.trim(),
        label: label.trim(),
        is_active: Boolean(isActive)
      });
      setCode("");
      setLabel("");
      setIsActive(true);
      setNotice("Département créé.");
      await loadAll();
    } catch (e) {
      const err = e as ApiError;
      setError(err.bodyText || err.message);
    } finally {
      setLoading(false);
    }
  }

  function openEdit(d: Department) {
    setEditTarget(d);
    setEditLabel(d.label || "");
    setEditIsActive(Boolean(d.is_active));
    setEditOpen(true);
  }

  async function saveEdit() {
    if (!editTarget) return;
    setError(null);
    setNotice(null);
    setLoading(true);
    try {
      const body: any = {};
      if (editLabel.trim() && editLabel.trim() !== editTarget.label) body.label = editLabel.trim();
      if (editIsActive !== editTarget.is_active) body.is_active = editIsActive;
      await api.put<Department>(`/departments/${encodeURIComponent(editTarget.code)}`, body);
      setEditOpen(false);
      setEditTarget(null);
      setNotice("Département mis à jour.");
      await loadAll();
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
        title="Départements"
        subtitle="Créer/activer/désactiver les départements (réservé SUPER_ADMIN)."
        right={
          <Button variant="contained" startIcon={<AddOutlinedIcon />} onClick={createDepartment} disabled={!canCreate || loading}>
            Créer
          </Button>
        }
      />

      {error ? <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert> : null}
      {notice ? <Alert severity="info" sx={{ mb: 2 }}>{notice}</Alert> : null}

      <Paper elevation={0} sx={{ p: 3, borderRadius: 3, mb: 2 }}>
        <Stack spacing={2}>
          <Typography variant="subtitle1">Nouveau département</Typography>
          <Stack direction={{ xs: "column", md: "row" }} spacing={2} alignItems={{ md: "center" }}>
            <TextField
              label="Code (ex: FINANCE)"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              fullWidth
            />
            <TextField
              label="Libellé"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              fullWidth
            />
            <FormControlLabel
              control={<Switch checked={isActive} onChange={(e) => setIsActive(e.target.checked)} />}
              label="Actif"
            />
          </Stack>
        </Stack>
      </Paper>

      <Paper elevation={0} sx={{ p: 3, borderRadius: 3 }}>
        <Stack spacing={1.25}>
          <Typography variant="subtitle1">Liste</Typography>
          {(items || []).map((d) => (
            <Paper key={d.code} variant="outlined" sx={{ p: 1.5 }}>
              <Stack direction={{ xs: "column", sm: "row" }} spacing={1} alignItems={{ sm: "center" }}>
                <Stack direction="row" spacing={1} alignItems="center" sx={{ flex: 1 }}>
                  <BusinessOutlinedIcon fontSize="small" />
                  <Typography variant="body2" sx={{ fontWeight: 600 }}>
                    {d.code}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    — {d.label}
                  </Typography>
                  <Typography variant="caption" color={d.is_active ? "success.main" : "text.secondary"}>
                    {d.is_active ? "Actif" : "Inactif"}
                  </Typography>
                </Stack>
                <Button
                  variant="outlined"
                  startIcon={<EditOutlinedIcon />}
                  onClick={() => openEdit(d)}
                  disabled={loading}
                >
                  Modifier
                </Button>
              </Stack>
            </Paper>
          ))}
          {items.length === 0 ? (
            <Typography variant="body2" color="text.secondary">
              Aucun département.
            </Typography>
          ) : null}
        </Stack>
      </Paper>

      <Dialog open={editOpen} onClose={() => setEditOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>Modifier {editTarget?.code || ""}</DialogTitle>
        <DialogContent sx={{ pt: 1 }}>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField label="Libellé" value={editLabel} onChange={(e) => setEditLabel(e.target.value)} fullWidth />
            <FormControlLabel
              control={<Switch checked={editIsActive} onChange={(e) => setEditIsActive(e.target.checked)} />}
              label="Actif"
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setEditOpen(false)} disabled={loading}>
            Annuler
          </Button>
          <Button variant="contained" onClick={saveEdit} disabled={loading || !editTarget}>
            Enregistrer
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}

