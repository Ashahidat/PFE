import {
  Alert,
  Box,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  FormControl,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Stack,
  TextField,
  Typography
} from "@mui/material";
import PageHeader from "../components/PageHeader";
import { useEffect, useMemo, useState } from "react";
import { api, ApiError } from "../lib/api";
import { getEmployeeId, getUserRole } from "../lib/storage";

type Department = { code: string; label: string; is_active: boolean };
type UserItem = {
  employee_id: string;
  username: string;
  department: string;
  role: string;
  is_protected: boolean;
  is_active: boolean;
};
type RoleCount = { role: string; count: number; limit: number };

const CRITICAL_ROLES = new Set(["SUPER_ADMIN", "ADMIN_GLOSSAIRE"]);

export default function UsersAdminPage() {
  const role = getUserRole();
  const me = getEmployeeId();
  const isSuperAdmin = role === "SUPER_ADMIN";

  const [departments, setDepartments] = useState<Department[]>([]);
  const [items, setItems] = useState<UserItem[]>([]);
  const [counts, setCounts] = useState<RoleCount[]>([]);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  // Create form
  const [createOpen, setCreateOpen] = useState(false);
  const [employeeId, setEmployeeId] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [department, setDepartment] = useState<string>("");
  const [userRole, setUserRole] = useState<string>("DATA_OWNER");
  const canCreate = useMemo(
    () => employeeId.trim() && username.trim() && password.trim() && department.trim() && userRole.trim(),
    [employeeId, username, password, department, userRole]
  );

  // Edit dialog
  const [editOpen, setEditOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<UserItem | null>(null);
  const [editUsername, setEditUsername] = useState("");
  const [editPassword, setEditPassword] = useState("");
  const [editDepartment, setEditDepartment] = useState("");
  const [editRole, setEditRole] = useState("");
  const [editIsActive, setEditIsActive] = useState(true);

  const canEditTarget = useMemo(() => {
    if (!editTarget) return false;
    if (editTarget.employee_id === me) return true;
    if (editTarget.role === "SUPER_ADMIN" && !isSuperAdmin) return false;
    if (editTarget.is_protected && !isSuperAdmin) return false;
    return true;
  }, [editTarget, isSuperAdmin, me]);

  async function loadAll() {
    setError(null);
    setNotice(null);
    setLoading(true);
    try {
      const [depts, users, roleCounts] = await Promise.all([
        api.get<Department[]>("/departments"),
        api.get<UserItem[]>("/users"),
        api.get<RoleCount[]>("/users/role-counts").catch(() => [])
      ]);
      setDepartments(depts || []);
      setItems((users || []).filter((u) => u.employee_id !== me));
      setCounts(roleCounts || []);
      if (!department && depts?.length) setDepartment(depts[0].code);
      if (!editDepartment && depts?.length) setEditDepartment(depts[0].code);
    } catch (e) {
      const err = e as ApiError;
      setError(err.bodyText || err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function openEdit(u: UserItem) {
    setEditTarget(u);
    setEditUsername(u.username);
    setEditPassword("");
    setEditDepartment(u.department || "");
    setEditRole(u.role);
    setEditIsActive(Boolean(u.is_active));
    setEditOpen(true);
  }

  async function createUser() {
    if (!canCreate) return;
    setError(null);
    setNotice(null);
    setLoading(true);
    try {
      await api.post<UserItem>("/users", {
        employee_id: employeeId.trim(),
        username: username.trim(),
        password,
        department: department.trim(),
        role: userRole
      });
      setCreateOpen(false);
      setEmployeeId("");
      setUsername("");
      setPassword("");
      setUserRole("DATA_OWNER");
      setNotice("Utilisateur créé.");
      await loadAll();
    } catch (e) {
      const err = e as ApiError;
      setError(err.bodyText || err.message);
    } finally {
      setLoading(false);
    }
  }

  async function saveEdit() {
    if (!editTarget) return;
    setError(null);
    setNotice(null);
    setLoading(true);
    try {
      const body: any = {};
      if (editUsername.trim() && editUsername.trim() !== editTarget.username) body.username = editUsername.trim();
      if (editPassword.trim()) body.password = editPassword;
      if (editDepartment.trim() && editDepartment.trim() !== editTarget.department) body.department = editDepartment.trim();
      if (editRole && editRole !== editTarget.role) body.role = editRole;
      if (editIsActive !== editTarget.is_active) body.is_active = editIsActive;
      await api.put<UserItem>(`/users/${encodeURIComponent(editTarget.employee_id)}`, body);
      setEditOpen(false);
      setEditTarget(null);
      setNotice("Utilisateur mis à jour.");
      await loadAll();
    } catch (e) {
      const err = e as ApiError;
      setError(err.bodyText || err.message);
    } finally {
      setLoading(false);
    }
  }

  function roleChipColor(r: string): "default" | "success" | "warning" | "error" {
    if (r === "SUPER_ADMIN") return "error";
    if (r === "ADMIN_GLOSSAIRE") return "warning";
    if (r === "ADMIN") return "success";
    return "default";
  }

  const roleOptions = [
    { value: "DATA_OWNER", label: "DATA_OWNER — propriétaire de data" },
    { value: "ADMIN", label: "ADMIN — admin applicatif" },
    { value: "ADMIN_GLOSSAIRE", label: "ADMIN_GLOSSAIRE — gestion glossaire" },
    { value: "SUPER_ADMIN", label: "SUPER_ADMIN — super-admin" },
    { value: "AUDIT", label: "AUDIT — lecture" }
  ];

  return (
    <Box>
      <PageHeader
        title="Gestion des utilisateurs"
        subtitle="Créer et gérer les comptes (rôle, département, activation)."
        right={
          <Button variant="contained" onClick={() => setCreateOpen(true)}>
            Créer un utilisateur
          </Button>
        }
      />

      {error ? <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert> : null}
      {notice ? <Alert severity="info" sx={{ mb: 2 }}>{notice}</Alert> : null}

      {counts?.length ? (
        <Paper elevation={0} sx={{ p: 2.5, borderRadius: 3, mb: 2 }}>
          <Typography variant="subtitle1" sx={{ mb: 1 }}>
            Capacités des rôles critiques
          </Typography>
          <Stack direction="row" spacing={1} flexWrap="wrap">
            {counts.map((c) => {
              const reached = c.limit > 0 && c.count >= c.limit;
              return (
                <Chip
                  key={c.role}
                  color={reached ? "warning" : "default"}
                  label={`${c.role}: ${c.limit > 0 ? `${c.count}/${c.limit}` : `${c.count} (no limit)`}`}
                  variant={reached ? "filled" : "outlined"}
                />
              );
            })}
          </Stack>
        </Paper>
      ) : null}

      <Paper elevation={0} sx={{ p: 3, borderRadius: 3 }}>
        <Stack spacing={1}>
          {(items || []).map((u) => (
            <Paper key={u.employee_id} variant="outlined" sx={{ p: 1.5 }}>
              <Stack direction={{ xs: "column", sm: "row" }} spacing={1} alignItems={{ sm: "center" }}>
                <Box sx={{ flex: 1 }}>
                  <Typography variant="body2">
                    <strong>{u.employee_id}</strong> — {u.username}{" "}
                    <Typography component="span" variant="caption" color="text.secondary">
                      ({u.department})
                    </Typography>
                  </Typography>
                  <Stack direction="row" spacing={1} flexWrap="wrap" sx={{ mt: 0.5 }}>
                    <Chip size="small" label={u.role} color={roleChipColor(u.role)} />
                    <Chip size="small" label={u.is_active ? "Actif" : "Inactif"} variant="outlined" />
                    {u.is_protected ? <Chip size="small" label="Protégé" color="warning" variant="outlined" /> : null}
                  </Stack>
                </Box>
                <Button variant="outlined" onClick={() => openEdit(u)} disabled={loading}>
                  Modifier
                </Button>
              </Stack>
            </Paper>
          ))}
          {items.length === 0 ? (
            <Typography variant="body2" color="text.secondary">
              Aucun utilisateur à afficher.
            </Typography>
          ) : null}
        </Stack>
      </Paper>

      <Dialog open={createOpen} onClose={() => setCreateOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>Créer un utilisateur</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField label="Employee ID" value={employeeId} onChange={(e) => setEmployeeId(e.target.value)} />
            <TextField label="Username" value={username} onChange={(e) => setUsername(e.target.value)} />
            <TextField
              label="Mot de passe"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            <FormControl fullWidth>
              <InputLabel id="dept">Département</InputLabel>
              <Select labelId="dept" label="Département" value={department} onChange={(e) => setDepartment(String(e.target.value))}>
                {departments.map((d) => (
                  <MenuItem key={d.code} value={d.code}>
                    {d.label} ({d.code})
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <FormControl fullWidth>
              <InputLabel id="role">Rôle</InputLabel>
              <Select labelId="role" label="Rôle" value={userRole} onChange={(e) => setUserRole(String(e.target.value))}>
                {roleOptions.map((r) => (
                  <MenuItem
                    key={r.value}
                    value={r.value}
                    disabled={!isSuperAdmin && CRITICAL_ROLES.has(r.value)}
                  >
                    {r.label}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            {!isSuperAdmin ? (
              <Alert severity="info">
                Les rôles critiques ({Array.from(CRITICAL_ROLES).join(", ")}) ne sont assignables que par un SUPER_ADMIN.
              </Alert>
            ) : null}
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCreateOpen(false)}>Annuler</Button>
          <Button variant="contained" onClick={createUser} disabled={!canCreate || loading}>
            Créer
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog open={editOpen} onClose={() => setEditOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>Modifier l'utilisateur</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            {editTarget ? (
              <Alert severity="info">
                Cible: <strong>{editTarget.employee_id}</strong>
              </Alert>
            ) : null}
            <TextField
              label="Username"
              value={editUsername}
              onChange={(e) => setEditUsername(e.target.value)}
              disabled={!canEditTarget}
            />
            <TextField
              label="Nouveau mot de passe (optionnel)"
              type="password"
              value={editPassword}
              onChange={(e) => setEditPassword(e.target.value)}
              disabled={!canEditTarget}
            />
            <FormControl fullWidth>
              <InputLabel id="edit-dept">Département</InputLabel>
              <Select
                labelId="edit-dept"
                label="Département"
                value={editDepartment}
                onChange={(e) => setEditDepartment(String(e.target.value))}
                disabled={!canEditTarget}
              >
                {departments.map((d) => (
                  <MenuItem key={d.code} value={d.code}>
                    {d.label} ({d.code})
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <FormControl fullWidth>
              <InputLabel id="edit-role">Rôle</InputLabel>
              <Select
                labelId="edit-role"
                label="Rôle"
                value={editRole}
                onChange={(e) => setEditRole(String(e.target.value))}
                disabled={!canEditTarget}
              >
                {roleOptions.map((r) => (
                  <MenuItem
                    key={r.value}
                    value={r.value}
                    disabled={!isSuperAdmin && CRITICAL_ROLES.has(r.value)}
                  >
                    {r.label}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            <Divider />

            <Stack direction="row" spacing={1} alignItems="center">
              <Chip label={editIsActive ? "Actif" : "Inactif"} variant="outlined" />
              <Button
                variant="outlined"
                color={editIsActive ? "warning" : "success"}
                onClick={() => setEditIsActive((v) => !v)}
                disabled={!canEditTarget}
              >
                {editIsActive ? "Désactiver" : "Activer"}
              </Button>
            </Stack>

            {!canEditTarget ? (
              <Alert severity="warning">
                Pas de droits pour modifier cet utilisateur (super-admin / protégé).
              </Alert>
            ) : null}
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setEditOpen(false)}>Annuler</Button>
          <Button variant="contained" onClick={saveEdit} disabled={!editTarget || loading || !canEditTarget}>
            Enregistrer
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
