import {
  Alert,
  Box,
  Button,
  Chip,
  Divider,
  LinearProgress,
  Paper,
  Stack,
  Typography,
  Accordion,
  AccordionDetails,
  AccordionSummary
} from "@mui/material";
import ExpandMoreOutlinedIcon from "@mui/icons-material/ExpandMoreOutlined";
import RefreshOutlinedIcon from "@mui/icons-material/RefreshOutlined";
import CheckCircleOutlineOutlinedIcon from "@mui/icons-material/CheckCircleOutlineOutlined";
import WarningAmberOutlinedIcon from "@mui/icons-material/WarningAmberOutlined";
import DoDisturbOnOutlinedIcon from "@mui/icons-material/DoDisturbOnOutlined";
import PageHeader from "../components/PageHeader";
import AtlasUiLinkButton from "../components/AtlasUiLinkButton";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError } from "../lib/api";
import { getLastDagRunId, getLastDatasetId, setLastDatasetId } from "../lib/storage";

type ResultItem = {
  rule_type?: string;
  column_name?: string | null;
  status?: string;
  error_count?: number;
  ratio?: string;
  examples?: any[];
};

type FriendlyRule = {
  title: string;
  explanation: string;
  whatItChecks: string;
};

type NoticeSeverity = "success" | "info" | "warning" | "error";

function normalizeStatus(status?: string): "success" | "error" | "warning" | "default" {
  const s = String(status || "").toLowerCase();
  if (["réussi", "success", "pass"].includes(s)) return "success";
  if (["échoué", "failed", "fail"].includes(s)) return "error";
  if (["ignoré", "skipped"].includes(s)) return "warning";
  return "default";
}

function friendlyStatus(status?: string) {
  const tone = normalizeStatus(status);
  if (tone === "success") return { label: "OK", tone };
  if (tone === "error") return { label: "À vérifier", tone };
  if (tone === "warning") return { label: "Ignoré", tone };
  return { label: String(status || "Inconnu"), tone };
}

function isTerminalState(state?: string | null) {
  const s = String(state || "").toLowerCase();
  return ["success", "failed", "error", "cancelled", "canceled", "skipped", "done", "finished"].includes(s);
}

function humanizeRule(ruleType?: string): FriendlyRule {
  const raw = String(ruleType || "").trim();
  if (!raw) {
    return {
      title: "Contrôle",
      explanation: "Un contrôle de qualité a été appliqué.",
      whatItChecks: "Ce qu'on vérifie n'est pas précisé dans ce résultat."
    };
  }

  if (raw.startsWith("ml_profile_")) {
    return {
      title: "Analyse intelligente de cohérence",
      explanation: "Le système compare cette colonne à ce qu'il s'attend à voir dans ce type de données.",
      whatItChecks: "On cherche des colonnes qui ressemblent trop à un identifiant, une valeur atypique ou une forme différente du reste du fichier."
    };
  }

  const directMap: Record<string, FriendlyRule> = {
    "doublons sur ligne entière": {
      title: "Doublons sur des lignes complètes",
      explanation: "On vérifie si des lignes identiques se répètent dans le fichier.",
      whatItChecks: "Deux lignes exactement identiques sont comptées comme doublons."
    },
    regex: {
      title: "Contrôle de format",
      explanation: "On vérifie si les valeurs suivent le format attendu.",
      whatItChecks: "Exemple: email, téléphone, code postal ou autre motif précis."
    },
    deequ: {
      title: "Contrôle de cohérence",
      explanation: "On vérifie des règles de qualité sur les valeurs.",
      whatItChecks: "Ce contrôle peut tester les valeurs manquantes, les bornes ou d'autres règles définies."
    }
  };

  if (directMap[raw]) return directMap[raw];

  const clean = raw
    .replace(/_/g, " ")
    .replace(/\s+/g, " ")
    .trim();

  return {
    title: clean.charAt(0).toUpperCase() + clean.slice(1),
    explanation: "Un contrôle automatique a été appliqué à cette colonne.",
    whatItChecks: "Les détails techniques du contrôle sont disponibles plus bas."
  };
}

function examplesToText(examples?: any[]) {
  if (!Array.isArray(examples) || examples.length === 0) return [];
  return examples.filter((v) => typeof v === "string" && v.trim().length > 0).slice(0, 4);
}

export default function ResultsPage() {
  const navigate = useNavigate();
  const [items, setItems] = useState<ResultItem[]>([]);
  const [state, setState] = useState<string | null>(null);
  const [resolvedDatasetId, setResolvedDatasetId] = useState<string | null>(getLastDatasetId());
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [atlasNotice, setAtlasNotice] = useState<{ message: string; severity: NoticeSeverity } | null>(null);
  const [atlasLoading, setAtlasLoading] = useState(false);
  const [atlasPushed, setAtlasPushed] = useState(false);
  const dagRunId = getLastDagRunId();

  useEffect(() => {
    if (!atlasPushed) return;
    const timer = window.setTimeout(() => {
      navigate("/uploads");
    }, 1400);
    return () => window.clearTimeout(timer);
  }, [atlasPushed, navigate]);

  const summary = useMemo(() => {
    let total = 0;
    let ok = 0;
    let failed = 0;
    let skipped = 0;

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

  const overviewText = useMemo(() => {
    if (!summary.total) return "Aucun contrôle à afficher pour le moment.";
    if (summary.failed > 0) {
      return `Sur ${summary.total} contrôles, ${summary.ok} sont rassurants et ${summary.failed} mérite${summary.failed > 1 ? "nt" : ""} une vérification humaine.`;
    }
    if (summary.skipped > 0) {
      const verb = summary.skipped > 1 ? "ont été" : "a été";
      return `Sur ${summary.total} contrôles, ${summary.ok} sont rassurants et ${summary.skipped} contrôle${summary.skipped > 1 ? "s" : ""} ${verb} ignoré${summary.skipped > 1 ? "s" : ""}.`;
    }
    return `Tous les ${summary.total} contrôles affichés sont rassurants.`;
  }, [summary]);

  async function loadOnce() {
    if (!dagRunId) return;
    setError(null);
    setLoading(true);
    try {
      const st = (await api
        .get<{ state: string; dataset_id?: string }>(`/dag-status/${dagRunId}`)
        .catch(() => ({ state: null as string | null, dataset_id: undefined as string | undefined }))) as {
        state: string | null;
        dataset_id?: string;
      };
      setState(st?.state || null);
      if (st?.dataset_id) {
        setResolvedDatasetId(st.dataset_id);
        setLastDatasetId(st.dataset_id);
      }

      const existing = await api.get<any>(`/results/${dagRunId}`).catch(() => []);
      if (Array.isArray(existing) && existing.length > 0) {
        setItems(existing);
        return;
      }

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

  useEffect(() => {
    if (!dagRunId) return;

    const refresh = () => {
      void loadOnce();
    };

    if (isTerminalState(state) && items.length > 0) {
      return;
    }

    const timer = window.setInterval(refresh, 4000);
    return () => window.clearInterval(timer);
  }, [dagRunId, items.length, state]);

  async function pushAtlas() {
    if (!resolvedDatasetId || atlasPushed) return;
    setAtlasNotice(null);
    setAtlasLoading(true);
    try {
      const res = await api.post<any>(`/push-atlas/${resolvedDatasetId}`, {});
      if (res?.already_synced) {
        setAtlasNotice({ severity: "info", message: "Le dataset a déjà été synchronisé avec Atlas." });
        setAtlasPushed(true);
        return;
      }
      const applied = typeof res?.column_classifications_applied === "number" ? res.column_classifications_applied : null;
      const errors = typeof res?.column_classifications_errors === "number" ? res.column_classifications_errors : null;
      const extra = [
        res?.dataset_guid ? "Identifiant Atlas reçu" : null,
        applied !== null ? `${applied} classification${applied > 1 ? "s" : ""} colonne${applied > 1 ? "s" : ""} appliquée${applied > 1 ? "s" : ""}` : null,
        errors !== null && errors > 0 ? `${errors} erreur${errors > 1 ? "s" : ""} de classification` : null
      ]
        .filter(Boolean)
        .join(" · ");
      setAtlasNotice({
        severity: "success",
        message: `Synchronisation Atlas terminée.${extra ? ` ${extra}` : ""}. Retour aux datasets en cours.`
      });
      setAtlasPushed(true);
    } catch (e) {
      const err = e as ApiError;
      setAtlasNotice({ severity: "error", message: `Synchronisation Atlas impossible. ${err.bodyText || err.message}` });
    } finally {
      setAtlasLoading(false);
    }
  }

  return (
    <Box>
      <PageHeader
        title="Résultats"
        subtitle={dagRunId ? `Run: ${dagRunId}` : "Aucun run sélectionné"}
        right={
          <Stack direction="row" spacing={1}>
            <AtlasUiLinkButton label="Ouvrir Atlas" variant="outlined" />
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
              disabled={!resolvedDatasetId || atlasLoading || atlasPushed || !isTerminalState(state)}
              onClick={pushAtlas}
              title={
                !resolvedDatasetId
                  ? "Dataset introuvable pour ce run"
                  : !isTerminalState(state)
                    ? "Le run doit être terminé avant la synchronisation Atlas"
                    : atlasPushed
                      ? "Atlas a déjà été finalisé pour ce run"
                      : undefined
              }
            >
              Finaliser Atlas
            </Button>
          </Stack>
        }
      />

      {error ? <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert> : null}
      {!dagRunId ? <Alert severity="info">Lance une validation depuis "Valider qualité" pour voir les résultats ici.</Alert> : null}
      {dagRunId ? (
        <Alert severity={isTerminalState(state) ? "success" : "info"} sx={{ mb: 2 }}>
          {isTerminalState(state)
            ? "Le traitement est terminé. Les résultats ci-dessous sont à jour."
            : "Le traitement est en cours. La page se met à jour automatiquement toutes les 4 secondes."}
        </Alert>
      ) : null}

      {loading ? <LinearProgress sx={{ mb: 2 }} /> : null}
      {atlasNotice ? <Alert severity={atlasNotice.severity} sx={{ mb: 2 }}>{atlasNotice.message}</Alert> : null}

      {dagRunId ? (
        <Paper
          elevation={0}
          sx={{
            borderRadius: 3,
            p: 2.5,
            mb: 2,
            background: "linear-gradient(135deg, rgba(30,64,175,0.08), rgba(15,118,110,0.08))"
          }}
        >
          <Stack spacing={1.5}>
            <Box>
              <Typography variant="h6" sx={{ mb: 0.5 }}>
                Lecture simple
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {overviewText} Un statut "À vérifier" ne veut pas dire qu'il y a forcément une erreur grave. Cela veut
                juste dire qu'une colonne mérite un regard humain avant la publication.
              </Typography>
            </Box>

            <Stack direction="row" spacing={1} flexWrap="wrap">
              <Chip label={`Contrôles: ${summary.total}`} />
              <Chip color="success" icon={<CheckCircleOutlineOutlinedIcon />} label={`Rassurants: ${summary.ok}`} />
              <Chip color="error" icon={<WarningAmberOutlinedIcon />} label={`À vérifier: ${summary.failed}`} />
              <Chip color="warning" icon={<DoDisturbOnOutlinedIcon />} label={`Ignorés: ${summary.skipped}`} />
              <Chip variant="outlined" label={`État: ${state || "?"}`} />
              {resolvedDatasetId ? <Chip variant="outlined" label={`Dataset: ${resolvedDatasetId}`} /> : null}
            </Stack>
          </Stack>
        </Paper>
      ) : null}

      <Stack spacing={1.5}>
        {(items || []).map((it, idx) => {
          const rule = humanizeRule(it.rule_type);
          const columnLabel = it.column_name || "Jeu de données entier";
          const status = friendlyStatus(it.status);
          const examples = examplesToText(it.examples);

          return (
            <Accordion key={idx} elevation={0} sx={{ borderRadius: 2, "&:before": { display: "none" }, overflow: "hidden" }}>
              <AccordionSummary expandIcon={<ExpandMoreOutlinedIcon />}>
                <Stack spacing={0.5} sx={{ width: "100%" }}>
                  <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap">
                    <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
                      {rule.title}
                    </Typography>
                    <Chip size="small" label={status.label} color={status.tone} />
                    <Chip size="small" variant="outlined" label={columnLabel} />
                  </Stack>
                  <Typography variant="body2" color="text.secondary">
                    {rule.explanation}
                  </Typography>
                </Stack>
              </AccordionSummary>
              <AccordionDetails>
                <Stack spacing={1.5}>
                  <Box>
                    <Typography variant="subtitle2" sx={{ mb: 0.5 }}>
                      Ce que cela veut dire
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      {rule.whatItChecks}
                    </Typography>
                  </Box>

                  <Box>
                    <Typography variant="subtitle2" sx={{ mb: 0.5 }}>
                      Interprétation
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      {status.tone === "success"
                        ? "Rien d'inquiétant n'a été détecté sur cette colonne."
                        : status.tone === "error"
                          ? "Cette colonne sort du profil attendu. Elle mérite d'être revue par une personne."
                          : status.tone === "warning"
                            ? "Le contrôle a été ignoré ou n'a pas pu être appliqué."
                            : "Le résultat est disponible mais son statut est moins clair."}
                    </Typography>
                  </Box>

                  <Box>
                    <Typography variant="subtitle2" sx={{ mb: 0.5 }}>
                      Indices techniques
                    </Typography>
                    <Stack direction="row" spacing={1} flexWrap="wrap">
                      <Chip size="small" variant="outlined" label={`Lignes concernées: ${it.error_count ?? 0}`} />
                      <Chip size="small" variant="outlined" label={`Ratio: ${it.ratio || "—"}`} />
                      <Chip size="small" variant="outlined" label={`Statut brut: ${it.status || "—"}`} />
                    </Stack>
                  </Box>

                  {examples.length > 0 ? (
                    <Box>
                      <Typography variant="subtitle2" sx={{ mb: 0.5 }}>
                        Exemples
                      </Typography>
                      <Stack spacing={0.5}>
                        {examples.map((ex, exIdx) => (
                          <Typography key={exIdx} variant="body2" color="text.secondary">
                            {ex}
                          </Typography>
                        ))}
                      </Stack>
                    </Box>
                  ) : null}
                </Stack>
              </AccordionDetails>
            </Accordion>
          );
        })}

        {items.length === 0 ? (
          <Paper elevation={0} sx={{ borderRadius: 2, p: 3 }}>
            <Typography variant="body2" color="text.secondary">
              Aucun résultat pour le moment.
            </Typography>
          </Paper>
        ) : null}
      </Stack>

      <Divider sx={{ my: 3 }} />

      <Alert severity="info">
        Astuce de lecture: si un contrôle est en "À vérifier", cela ne veut pas dire que le fichier est mauvais. Cela veut dire qu'une colonne attire l'attention et qu'il faut confirmer si c'est normal dans ton contexte.
      </Alert>
    </Box>
  );
}
