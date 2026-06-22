import { LoadingButton } from "@mui/lab";
import {
  Alert,
  Box,
  Container,
  Link,
  Paper,
  Stack,
  TextField,
  Typography
} from "@mui/material";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError } from "../lib/api";
import {
  setEmployeeId as setStoredEmployeeId,
  setToken,
  setUserDepartment,
  setUserRole,
  setUsername as setStoredUsername
} from "../lib/storage";

type LoginResponse = {
  access_token: string;
  token_type: string;
  username: string;
  role: string;
  department: string;
  employee_id: string;
};

export default function LoginPage() {
  const navigate = useNavigate();
  const [employeeId, setEmployeeId] = useState("");
  const [username, setUsername] = useState("");
  const [department, setDepartment] = useState("ADMIN");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canSubmit = useMemo(() => employeeId.trim() && password.trim(), [employeeId, password]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const payload: Record<string, unknown> = {
        employee_id: employeeId.trim(),
        password
      };
      if (username.trim()) payload.username = username.trim();
      if (department.trim()) payload.department = department.trim();
      const res = await api.post<LoginResponse>("/login", payload);
      setToken(res.access_token);
      setStoredUsername(res.username);
      setUserRole(res.role);
      setUserDepartment(res.department);
      setStoredEmployeeId(res.employee_id);
      navigate("/home");
    } catch (err) {
      const e2 = err as ApiError;
      if (e2 instanceof ApiError) {
        setError(e2.bodyText || e2.message);
      } else {
        setError("Erreur inconnue.");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <Box sx={{ minHeight: "100vh", display: "grid", placeItems: "center", bgcolor: "background.default", p: 2 }}>
      <Container maxWidth="sm">
        <Paper elevation={0} sx={{ p: 4, borderRadius: 4 }}>
          <Stack spacing={2}>
            <Typography variant="h5">Connexion</Typography>
            <Typography variant="body2" color="text.secondary">
              Accedez plateforme Qualité & Gouvernance des donnéesI. Entrez votre Employee ID et mot de passe pour vous connecter. 
            </Typography>
            {error ? <Alert severity="error">{error}</Alert> : null}

            <Box component="form" onSubmit={onSubmit}>
              <Stack spacing={2}>
                <TextField
                  label="Employee ID"
                  value={employeeId}
                  onChange={(e) => setEmployeeId(e.target.value)}
                  autoComplete="username"
                  required
                />
                <TextField
                  label="Mot de passe"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  type="password"
                  autoComplete="current-password"
                  required
                />
                {/* <TextField
                  label="Username (optionnel au bootstrap)"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                />
                <TextField
                  label="Département "
                  value={department}
                  onChange={(e) => setDepartment(e.target.value)}
                /> */}
                <LoadingButton loading={loading} variant="contained" type="submit" disabled={!canSubmit}>
                  Se connecter
                </LoadingButton>
              </Stack>
            </Box>

            <Typography variant="caption" color="text.secondary">
              Astuce: au premier lancement, le 1er utilisateur devient SUPER_ADMIN (voir backend `/login`).
            </Typography>
            {/* <Link href="/app" underline="hover" sx={{ fontSize: 13 }}>
              Ouvrir l'application React
            </Link> */}
          </Stack>
        </Paper>
      </Container>
    </Box>
  );
}
