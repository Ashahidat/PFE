import { Navigate, Route, Routes } from "react-router-dom";
import { Alert, Box, Button, Stack, Typography } from "@mui/material";
import Shell from "./Shell";
import LoginPage from "../pages/LoginPage";
import HomePage from "../pages/HomePage";
import ProjectsPage from "../pages/ProjectsPage";
import ProjectDetailsPage from "../pages/ProjectDetailsPage";
import UploadPage from "../pages/UploadPage";
import RunTestsPage from "../pages/RunTestsPage";
import ResultsPage from "../pages/ResultsPage";
import DescribePage from "../pages/DescribePage";
import GlossaryAdminPage from "../pages/GlossaryAdminPage";
import UsersAdminPage from "../pages/UsersAdminPage";
import DepartmentsAdminPage from "../pages/DepartmentsAdminPage";
import MyUploadsPage from "../pages/MyUploadsPage";
import ProfilePage from "../pages/ProfilePage";
import { getToken, getUserRole } from "../lib/storage";
import React from "react";

function RequireAuth({ children }: { children: React.ReactNode }) {
  const token = getToken();
  if (!token) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function RequireNotAudit({ children }: { children: React.ReactNode }) {
  const role = getUserRole();
  if (role === "AUDIT") return <Navigate to="/projects" replace />;
  return <>{children}</>;
}

function RequireRole({ roles, children }: { roles: string[]; children: React.ReactNode }) {
  const role = getUserRole();
  if (role === "SUPER_ADMIN") return <>{children}</>;
  if (!role || !roles.includes(role)) return <Navigate to="/projects" replace />;
  return <>{children}</>;
}

class AppErrorBoundary extends React.Component<
  { children: React.ReactNode },
  { hasError: boolean; message: string }
> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { hasError: false, message: "" };
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, message: error?.message || "Erreur d'affichage" };
  }

  componentDidCatch(error: Error) {
    console.error("[AppErrorBoundary]", error);
  }

  render() {
    if (this.state.hasError) {
      return (
        <Box sx={{ p: 4, maxWidth: 900, mx: "auto" }}>
          <Alert severity="error" sx={{ mb: 2 }}>
            Une page a planté pendant l’affichage. L’interface évite maintenant l’écran blanc.
          </Alert>
          <Stack spacing={2}>
            <Typography variant="h5">Erreur d’interface</Typography>
            <Typography variant="body2" color="text.secondary">
              {this.state.message || "Un composant React a levé une erreur."}
            </Typography>
            <Button variant="contained" onClick={() => window.location.reload()}>
              Recharger la page
            </Button>
          </Stack>
        </Box>
      );
    }

    return this.props.children;
  }
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/"
        element={
          <RequireAuth>
            <AppErrorBoundary>
              <Shell />
            </AppErrorBoundary>
          </RequireAuth>
        }
      >
        <Route index element={<Navigate to="home" replace />} />
        <Route path="home" element={<HomePage />} />
        <Route path="projects" element={<ProjectsPage />} />
        <Route path="projects/:projectId" element={<ProjectDetailsPage />} />
        <Route
          path="upload"
          element={
            <RequireNotAudit>
              <UploadPage />
            </RequireNotAudit>
          }
        />
        <Route
          path="describe"
          element={
            <RequireNotAudit>
              <DescribePage />
            </RequireNotAudit>
          }
        />
        <Route
          path="run"
          element={
            <RequireNotAudit>
              <RunTestsPage />
            </RequireNotAudit>
          }
        />
        <Route
          path="uploads"
          element={
            <RequireNotAudit>
              <MyUploadsPage />
            </RequireNotAudit>
          }
        />
        <Route
          path="users"
          element={
            <RequireRole roles={["ADMIN", "ADMIN_GLOSSAIRE"]}>
              <UsersAdminPage />
            </RequireRole>
          }
        />
        <Route
          path="departments"
          element={
            <RequireRole roles={[]}>
              <DepartmentsAdminPage />
            </RequireRole>
          }
        />
        <Route path="profile" element={<ProfilePage />} />
        <Route path="results" element={<ResultsPage />} />
        <Route
          path="glossary"
          element={
            <RequireRole roles={["ADMIN", "ADMIN_GLOSSAIRE"]}>
              <GlossaryAdminPage />
            </RequireRole>
          }
        />
        <Route path="*" element={<Navigate to="home" replace />} />
      </Route>
    </Routes>
  );
}
