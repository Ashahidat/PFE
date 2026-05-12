import {
  Alert,
  Box,
  Button,
  Chip,
  LinearProgress,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography
} from "@mui/material";
import RefreshOutlinedIcon from "@mui/icons-material/RefreshOutlined";
import PageHeader from "../components/PageHeader";
import { useEffect, useMemo, useState } from "react";
import { api, ApiError } from "../lib/api";
import { getLastDagRunId, getLastDatasetId } from "../lib/storage";

type ResultItem = {
  rule_type?: string;
  column_name?: string | null;
  status?: string;
  error_count?: number;
  ratio?: string;
  examples?: any[];
};

function statusColor(status?: string): "success" | "error" | "warning" | "default" {
  const s = String(status || "").toLowerCase();
  if (["réussi", "success", "pass"].includes(s)) return "success";
  if (["échoué", "failed", "fail"].includes(s)) return "error";
  if (["ignoré", "skipped"].includes(s)) return "warning";
  return "default";
}

export default function ResultsPage() {
  const [items, setItems] = useState<ResultItem[]>([]);
  const [state, setState] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [atlasMsg, setAtlasMsg] = useState<string | null>(null);
  const [atlasLoading, setAtlasLoading] = useState(false);
  const dagRunId = getLastDagRunId();
  const datasetId = getLastDatasetId();

  const summary = useMemo(() => {
    let total = 0,
      ok = 0,
      failed = 0,
      skipped = 0;
    for (const it of items) {
      if (!it?.status) continue;
      total += 1;
      const s = String(it.status).toLowerCase();
      if (["réussi", "success", "pass"].includes(s)) ok += 1;
      else if (["échoué", "failed", "fail"].includes(s)) failed += 1;
      else if (["ignoré", "skipped"].includes(s)) skipped += 1;
    }
    return { total, ok, failed, skipped };
  }, [items]);

  async function loadOnce() {
    if (!dagRunId) return;
    setError(null);
    setLoading(true);
    try {
      const existing = await api.get<any>(`/results/${dagRunId}`).catch(() => []);
      if (Array.isArray(existing) && existing.length > 0) {
        setItems(existing);
        setState("success");
        return;
      }

      const st = await api.get<{ state: string }>(`/dag-status/${dagRunId}`).catch(() => ({ state: null as any }));
      setState(st?.state || null);
      if (st?.state === "success") {
        const res = await api.get<any>(`/results/${dagRunId}`).catch(() => []);
        setItems(Array.isArray(res) ? res : []);
      }
    } catch (e) {
      const err = e as ApiError;
      setError(err.bodyText || err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadOnce();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function pushAtlas() {
    if (!datasetId) return;
    setAtlasMsg(null);
    setAtlasLoading(true);
    try {
      const res = await api.post<any>(`/push-atlas/${datasetId}`, {});
      const applied = typeof res?.column_classifications_applied === "number" ? res.column_classifications_applied : null;
      const errors = typeof res?.column_classifications_errors === "number" ? res.column_classifications_errors : null;
      const extra = [
        res?.dataset_guid ? "Dataset guid reçu." : null,
        applied !== null ? `Classifications colonnes appliquées: ${applied}` : null,
        errors !== null && errors > 0 ? `Erreurs classification colonnes: ${errors}` : null
      ]
        .filter(Boolean)
        .join(" · ");
      setAtlasMsg(`✅ Push Atlas terminé.${extra ? ` ${extra}` : ""}`);
    } catch (e) {
      const err = e as ApiError;
      setAtlasMsg(`❌ Push Atlas impossible. ${err.bodyText || err.message}`);
    } finally {
      setAtlasLoading(false);
    }
  }

  return (
    <Box>
      <PageHeader
        title="Résultats"
        subtitle={dagRunId ? `DAG run: ${dagRunId}` : "Aucun run sélectionné"}
        right={
          <Stack direction="row" spacing={1}>
            <Button
              startIcon={<RefreshOutlinedIcon />}
              onClick={loadOnce}
              variant="outlined"
              disabled={!dagRunId || loading}
            >
              Rafraîchir
            </Button>
            <Button
              variant="contained"
              disabled={!datasetId || atlasLoading}
              onClick={pushAtlas}
              title={!datasetId ? "Uploader un dataset d'abord" : undefined}
            >
              Finaliser (push Atlas)
            </Button>
          </Stack>
        }
      />

      {error ? <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert> : null}
      {!dagRunId ? <Alert severity="info">Lance des validations depuis “Valider qualité”.</Alert> : null}

      {loading ? <LinearProgress sx={{ mb: 2 }} /> : null}
      {atlasMsg ? <Alert severity={atlasMsg.startsWith("✅") ? "success" : "error"} sx={{ mb: 2 }}>{atlasMsg}</Alert> : null}

      {dagRunId ? (
        <Stack direction="row" spacing={1} sx={{ mb: 2 }} flexWrap="wrap">
          <Chip label={`Total: ${summary.total}`} />
          <Chip color="success" label={`OK: ${summary.ok}`} />
          <Chip color="error" label={`Échecs: ${summary.failed}`} />
          <Chip color="warning" label={`Ignorés: ${summary.skipped}`} />
          <Chip variant="outlined" label={`State: ${state || "?"}`} />
        </Stack>
      ) : null}

      <Paper elevation={0} sx={{ borderRadius: 3, overflow: "hidden" }}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Règle</TableCell>
              <TableCell>Colonne</TableCell>
              <TableCell>Status</TableCell>
              <TableCell align="right">Erreurs</TableCell>
              <TableCell>Ratio</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {(items || []).map((it, idx) => (
              <TableRow key={idx} hover>
                <TableCell>
                  <Typography variant="body2">{it.rule_type || "—"}</Typography>
                </TableCell>
                <TableCell>{it.column_name || "—"}</TableCell>
                <TableCell>
                  <Chip size="small" label={it.status || "—"} color={statusColor(it.status)} />
                </TableCell>
                <TableCell align="right">{it.error_count ?? "—"}</TableCell>
                <TableCell>{it.ratio || "—"}</TableCell>
              </TableRow>
            ))}
            {items.length === 0 ? (
              <TableRow>
                <TableCell colSpan={5}>
                  <Typography variant="body2" color="text.secondary">
                    Aucun résultat pour le moment.
                  </Typography>
                </TableCell>
              </TableRow>
            ) : null}
          </TableBody>
        </Table>
      </Paper>
    </Box>
  );
}
