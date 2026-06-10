import { Outlet, useLocation, useNavigate } from "react-router-dom";
import {
  AppBar,
  Box,
  Divider,
  Drawer,
  IconButton,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Toolbar,
  Typography
} from "@mui/material";
import LogoutOutlinedIcon from "@mui/icons-material/LogoutOutlined";
import FolderOutlinedIcon from "@mui/icons-material/FolderOutlined";
import UploadFileOutlinedIcon from "@mui/icons-material/UploadFileOutlined";
import PlayCircleOutlinedIcon from "@mui/icons-material/PlayCircleOutlined";
import AssessmentOutlinedIcon from "@mui/icons-material/AssessmentOutlined";
import DescriptionOutlinedIcon from "@mui/icons-material/DescriptionOutlined";
import LibraryBooksOutlinedIcon from "@mui/icons-material/LibraryBooksOutlined";
import PeopleOutlinedIcon from "@mui/icons-material/PeopleOutlined";
import Inventory2OutlinedIcon from "@mui/icons-material/Inventory2Outlined";
import AccountCircleOutlinedIcon from "@mui/icons-material/AccountCircleOutlined";
import ShieldOutlinedIcon from "@mui/icons-material/ShieldOutlined";
import BusinessOutlinedIcon from "@mui/icons-material/BusinessOutlined";
import AtlasUiLinkButton from "../components/AtlasUiLinkButton";
import { clearToken, getUserRole } from "../lib/storage";

const drawerWidth = 264;

function buildNav(role: string | null) {
  const canUpload = role && role !== "AUDIT";
  const canManageGlossary = role && ["ADMIN", "ADMIN_GLOSSAIRE", "SUPER_ADMIN"].includes(role);
  const canManageUsers = role && ["ADMIN", "ADMIN_GLOSSAIRE", "SUPER_ADMIN"].includes(role);
  const canManageDepartments = role === "SUPER_ADMIN";
  const items = [{ to: "/projects", label: "Projets", icon: <FolderOutlinedIcon /> }];
  if (canUpload) {
    items.push({ to: "/uploads", label: "Mes uploads", icon: <Inventory2OutlinedIcon /> });
    items.push({ to: "/upload", label: "Upload dataset", icon: <UploadFileOutlinedIcon /> });
    items.push({ to: "/describe", label: "Descriptions", icon: <DescriptionOutlinedIcon /> });
    items.push({ to: "/run", label: "Valider qualité", icon: <PlayCircleOutlinedIcon /> });
  }
  items.push({ to: "/results", label: "Résultats", icon: <AssessmentOutlinedIcon /> });
  if (canManageGlossary) items.push({ to: "/glossary", label: "Glossaire", icon: <LibraryBooksOutlinedIcon /> });
  if (canManageUsers) items.push({ to: "/users", label: "Utilisateurs", icon: <PeopleOutlinedIcon /> });
  if (canManageDepartments) items.push({ to: "/departments", label: "Départements", icon: <BusinessOutlinedIcon /> });
  items.push({ to: "/profile", label: "Mon profil", icon: <AccountCircleOutlinedIcon /> });
  return items;
}

export default function Shell() {
  const location = useLocation();
  const navigate = useNavigate();
  const role = getUserRole();
  const nav = buildNav(role);

  return (
    <Box sx={{ display: "flex", minHeight: "100vh" }}>
      <AppBar position="fixed" elevation={0} sx={{ zIndex: (t) => t.zIndex.drawer + 1 }}>
        <Toolbar sx={{ gap: 1 }}>
          <ShieldOutlinedIcon />
          <Typography variant="h6" sx={{ flex: 1 }}>
            Data Quality & Governance
          </Typography>
          <AtlasUiLinkButton
            label="Atlas"
            variant="outlined"
            color="inherit"
            sx={{ borderColor: "rgba(255,255,255,0.4)" }}
          />
          <IconButton
            color="inherit"
            onClick={() => {
              clearToken();
              navigate("/login");
            }}
            aria-label="logout"
          >
            <LogoutOutlinedIcon />
          </IconButton>
        </Toolbar>
      </AppBar>

      <Drawer
        variant="permanent"
        sx={{
          width: drawerWidth,
          flexShrink: 0,
          [`& .MuiDrawer-paper`]: { width: drawerWidth, boxSizing: "border-box" }
        }}
      >
        <Toolbar />
        <Box sx={{ px: 2, py: 2 }}>
          <Typography variant="subtitle2" color="text.secondary">
            Navigation
          </Typography>
        </Box>
        <Divider />
        <List>
          {nav.map((item) => {
            const active = location.pathname === item.to || location.pathname.startsWith(item.to + "/");
            return (
              <ListItemButton
                key={item.to}
                selected={active}
                onClick={() => navigate(item.to)}
                sx={{ mx: 1, my: 0.5, borderRadius: 2 }}
              >
                <ListItemIcon>{item.icon}</ListItemIcon>
                <ListItemText primary={item.label} />
              </ListItemButton>
            );
          })}
        </List>
      </Drawer>

      <Box component="main" sx={{ flex: 1, p: 3 }}>
        <Toolbar />
        <Outlet />
      </Box>
    </Box>
  );
}
