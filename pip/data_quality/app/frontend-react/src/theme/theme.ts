import { createTheme } from "@mui/material/styles";

export const theme = createTheme({
  palette: {
    mode: "light",
    primary: { main: "#1E40AF" },
    secondary: { main: "#0F766E" },
    background: { default: "#F6F7FB", paper: "#FFFFFF" }
  },
  shape: { borderRadius: 12 },
  typography: {
    fontFamily:
      'ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, "Helvetica Neue", Arial, "Noto Sans", "Apple Color Emoji", "Segoe UI Emoji"'
  },
  components: {
    MuiPaper: { styleOverrides: { root: { backgroundImage: "none" } } }
  }
});

