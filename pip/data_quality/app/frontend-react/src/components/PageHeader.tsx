import { Box, Breadcrumbs, Link, Stack, Typography } from "@mui/material";
import { Link as RouterLink } from "react-router-dom";

export default function PageHeader(props: {
  title: string;
  subtitle?: string;
  crumbs?: Array<{ label: string; to?: string }>;
  right?: React.ReactNode;
}) {
  const { title, subtitle, crumbs, right } = props;
  return (
    <Stack direction="row" alignItems="flex-start" justifyContent="space-between" sx={{ mb: 2, gap: 2 }}>
      <Box>
        {crumbs?.length ? (
          <Breadcrumbs sx={{ mb: 0.5 }}>
            {crumbs.map((c, idx) =>
              c.to ? (
                <Link key={idx} component={RouterLink} underline="hover" to={c.to} color="inherit">
                  {c.label}
                </Link>
              ) : (
                <Typography key={idx} color="text.secondary">
                  {c.label}
                </Typography>
              )
            )}
          </Breadcrumbs>
        ) : null}
        <Typography variant="h5">{title}</Typography>
        {subtitle ? (
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
            {subtitle}
          </Typography>
        ) : null}
      </Box>
      {right ? <Box sx={{ pt: 0.5 }}>{right}</Box> : null}
    </Stack>
  );
}

