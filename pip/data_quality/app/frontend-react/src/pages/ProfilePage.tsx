import { LoadingButton } from "@mui/lab";
import { Alert, Box, Paper, Stack, TextField, Typography } from "@mui/material";
import PageHeader from "../components/PageHeader";
import { useEffect, useMemo, useState } from "react";
import { api, ApiError } from "../lib/api";
import { setUsername } from "../lib/storage";

type Me = { employee_id: string; username: string; department: string; role: string };

export default function ProfilePage() {
  const [me, setMe] = useState<Me | null>(null);
  const [newUsername, setNewUsername] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const canSave = useMemo(() => Boolean(newUsername.trim() || newPassword.trim()), [newUsername, newPassword]);

  async function load() {
    setError(null);
    setNotice(null);
    setLoading(true);
    try {
      const res = await api.get<Me>("/me");
      setMe(res);
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

  async function save() {
    if (!canSave) return;
    setError(null);
    setNotice(null);
    setLoading(true);
    try {
      const body: any = {};
      if (newUsername.trim()) body.username = newUsername.trim();
      if (newPassword.trim()) body.password = newPassword;
      const res = await api.put<Me>("/me", body);
      setMe(res);
      if (newUsername.trim()) setUsername(newUsername.trim());
      setNewUsername("");
      setNewPassword("");
      setNotice("Profil mis à jour.");
    } catch (e) {
      const err = e as ApiError;
      setError(err.bodyText || err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <Box>
      <PageHeader title="Mon profil" subtitle="Consulte tes infos et change ton username / mot de passe." />
      {error ? <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert> : null}
      {notice ? <Alert severity="info" sx={{ mb: 2 }}>{notice}</Alert> : null}

      <Paper elevation={0} sx={{ p: 3, borderRadius: 3 }}>
        <Stack spacing={2}>
          <Typography variant="subtitle1">Informations</Typography>
          <Stack spacing={0.5}>
            <Typography variant="body2">
              <strong>Employee ID:</strong> {me?.employee_id || "—"}
            </Typography>
            <Typography variant="body2">
              <strong>Username:</strong> {me?.username || "—"}
            </Typography>
            <Typography variant="body2">
              <strong>Département:</strong> {me?.department || "—"}
            </Typography>
            <Typography variant="body2">
              <strong>Rôle:</strong> {me?.role || "—"}
            </Typography>
          </Stack>

          <Typography variant="subtitle1" sx={{ mt: 1 }}>
            Modifier
          </Typography>
          <TextField
            label="Nouveau username (optionnel)"
            value={newUsername}
            onChange={(e) => setNewUsername(e.target.value)}
          />
          <TextField
            label="Nouveau mot de passe (optionnel)"
            type="password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
          />
          <LoadingButton loading={loading} variant="contained" disabled={!canSave} onClick={save}>
            Mettre à jour
          </LoadingButton>
        </Stack>
      </Paper>
    </Box>
  );
}

