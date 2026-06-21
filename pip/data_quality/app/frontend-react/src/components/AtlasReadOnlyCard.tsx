import OpenInNewOutlinedIcon from "@mui/icons-material/OpenInNewOutlined";
import { Box, Button, Paper, Stack, Typography } from "@mui/material";
import type { SxProps, Theme } from "@mui/material/styles";
import { ATLAS_UI_URL, canOpenAtlasUi } from "../lib/externalLinks";
import { getUserRole } from "../lib/storage";

type AtlasReadOnlyCardProps = {
  sx?: SxProps<Theme>;
};

export default function AtlasReadOnlyCard({ sx }: AtlasReadOnlyCardProps) {
  if (!canOpenAtlasUi(getUserRole())) return null;

  return (
    <Paper
      variant="outlined"
      sx={{
        p: 1.5,
        borderRadius: 2,
        background: "linear-gradient(180deg, rgba(15,118,110,0.05), rgba(30,64,175,0.03))",
        ...sx
      }}
    >
      <Stack spacing={0.75}>
        <Typography variant="caption" color="text.secondary" sx={{ textTransform: "uppercase", letterSpacing: 0.08 }}>
          Consulter
        </Typography>
        <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
          Atlas BETA UI
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Ouvre l’interface Atlas en lecture seule pour consulter le catalogue et naviguer dans les métadonnées.
        </Typography>
        <Box>
          <Button
            size="small"
            variant="outlined"
            component="a"
            href={ATLAS_UI_URL}
            target="_blank"
            rel="noopener noreferrer"
            endIcon={<OpenInNewOutlinedIcon />}
          >
            Ouvrir Atlas BETA UI
          </Button>
        </Box>
      </Stack>
    </Paper>
  );
}
