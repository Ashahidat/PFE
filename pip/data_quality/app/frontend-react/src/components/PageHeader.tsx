import { Box, Link, Stack, Typography } from "@mui/material";
import type { ReactNode } from "react";

export default function PageHeader(props: {
  title: string;
  subtitle?: string;
  crumbs?: Array<{ label: string; to?: string }>;
  right?: ReactNode;
}) {
  const { title, subtitle, crumbs, right } = props;
  return (
    <Stack direction="row" alignItems="flex-start" justifyContent="space-between" sx={{ mb: 2, gap: 2 }}>
      <Box>
        {crumbs?.length ? (
          <Stack direction="row" spacing={0.75} flexWrap="wrap" sx={{ mb: 0.5 }}>
            {crumbs.map((c, idx) =>
              c.to ? (
                <Link key={idx} href={c.to} underline="hover" color="inherit">
                  {c.label}
                </Link>
              ) : (
                <Typography key={idx} color="text.secondary">
                  {c.label}
                </Typography>
              )
            )}
          </Stack>
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
