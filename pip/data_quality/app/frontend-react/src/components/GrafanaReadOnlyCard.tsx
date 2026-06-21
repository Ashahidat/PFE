import { Box, Button, Paper, Stack, Typography } from "@mui/material";
import type { SxProps, Theme } from "@mui/material/styles";
import { toGrafanaBackendHref } from "../lib/externalLinks";

type GrafanaReadOnlyCardProps = {
  href?: string | null;
  sx?: SxProps<Theme>;
};

export default function GrafanaReadOnlyCard({ href, sx }: GrafanaReadOnlyCardProps) {
  const normalizedHref = toGrafanaBackendHref(href);
  if (!normalizedHref) return null;

  return (
    <Paper
      variant="outlined"
      sx={{
        p: 1.5,
        borderRadius: 2,
        background: "linear-gradient(180deg, rgba(30,64,175,0.04), rgba(15,118,110,0.03))",
        ...sx
      }}
    >
      <Stack spacing={0.75}>
        <Typography variant="caption" color="text.secondary" sx={{ textTransform: "uppercase", letterSpacing: 0.08 }}>
          Consulter
        </Typography>
        <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
          Dashboards Grafana (read-only)
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Ouvre les tableaux de bord Grafana en lecture seule. Les utilisateurs n’ont pas les droits d’édition.
        </Typography>
        <Box>
          <Button
            size="small"
            variant="outlined"
            component="a"
            href={normalizedHref}
            target="_blank"
            rel="noopener noreferrer"
          >
            Ouvrir Grafana
          </Button>
        </Box>
      </Stack>
    </Paper>
  );
}
