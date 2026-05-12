import { Navigate, Route, Routes } from "react-router-dom";
import Shell from "./Shell";
import LoginPage from "../pages/LoginPage";
import ProjectsPage from "../pages/ProjectsPage";
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

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/"
        element={
          <RequireAuth>
            <Shell />
          </RequireAuth>
        }
      >
        <Route index element={<Navigate to="projects" replace />} />
        <Route path="projects" element={<ProjectsPage />} />
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
        <Route path="*" element={<Navigate to="projects" replace />} />
      </Route>
    </Routes>
  );
}
