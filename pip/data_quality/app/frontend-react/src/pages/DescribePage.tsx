import {
  Alert,
  Box,
  Button,
  Chip,
  Divider,
  FormControl,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Stack,
  Tab,
  Tabs,
  TextField,
  Typography
} from "@mui/material";
import SaveOutlinedIcon from "@mui/icons-material/SaveOutlined";
import AddOutlinedIcon from "@mui/icons-material/AddOutlined";
import DeleteOutlineOutlinedIcon from "@mui/icons-material/DeleteOutlineOutlined";
import PageHeader from "../components/PageHeader";
import { useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { api, ApiError } from "../lib/api";
import { getLastDatasetId, getUserRole, setLastDatasetId } from "../lib/storage";

type DatasetItem = {
  id: string;
  name: string;
  columns: string[];
  columns_count: number;
  classification: "PUBLIC" | "DEPARTMENT";
  project?: { id: string; name: string; visibility: string } | null;
};

type SimpleInfo = { id: string; name: string; columns_list: string[]; description?: string | null };
type DescriptionRow = { column_name: string; description: string };
type InheritedDescriptionsResponse = {
  versions: {
    version_number: number;
    created_at?: string | null;
    descriptions: DescriptionRow[];
  }[];
};
type ParentSuggestion = {
  column_name: string;
  description: string;
  source_dataset?: string | null;
  source_version?: number | null;
  similarity_score?: number | null;
};
type ParentSuggestionsResponse = {
  has_parent: boolean;
  suggestions: ParentSuggestion[];
};
type ColumnClassRow = { column_name: string; classification_name: string };

type AllowedClassificationsResponse = {
  allowed: string[];
  dataset_classification: string | null;
  message?: string | null;
};

type GlossaryTerm = {
  id: number;
  term: string;
  description?: string | null;
  glossary_name?: string | null;
  category_name?: string | null;
};

type GlossaryAssignment = {
  id: number;
  glossary_term_id: number;
  term: string;
  glossary_name?: string | null;
  category_name?: string | null;
  column_name?: string | null;
};

// Source de chaque description : pour l'affichage d'un badge optionnel
type DescriptionSource = "manual" | "inherited" | "suggestion";

function useQuery() {
  const { search } = useLocation();
  return useMemo(() => new URLSearchParams(search), [search]);
}

function fillMissingDescriptions(
  base: Record<string, string>,
  rows: DescriptionRow[] | undefined,
  source: DescriptionSource,
  sourceMap: Record<string, DescriptionSource>
) {
  let filledCount = 0;

  for (const row of rows || []) {
    if (row.description?.trim() && !base[row.column_name]?.trim()) {
      base[row.column_name] = row.description;
      sourceMap[row.column_name] = source;
      filledCount++;
    }
  }

  return filledCount;
}

export default function DescribePage() {
  const q = useQuery();
  const navigate = useNavigate();
  const queryDatasetId = q.get("dataset_id") || "";
  const role = getUserRole();
  const canEdit = role !== "AUDIT";
  const canAssignGlossary = role && ["ADMIN", "ADMIN_GLOSSAIRE", "DATA_OWNER", "SUPER_ADMIN"].includes(role);

  const [tab, setTab] = useState<"descriptions" | "classifications" | "glossary">("descriptions");

  const [datasets, setDatasets] = useState<DatasetItem[]>([]);
  const [datasetId, setDatasetId] = useState<string>(queryDatasetId || getLastDatasetId() || "");
  const [info, setInfo] = useState<SimpleInfo | null>(null);

  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const [descriptions, setDescriptions] = useState<Record<string, string>>({});
  // Trace la source de chaque description pour un badge visuel optionnel
  const [descSources, setDescSources] = useState<Record<string, DescriptionSource>>({});
  const [allowed, setAllowed] = useState<AllowedClassificationsResponse | null>(null);
  const [colClasses, setColClasses] = useState<Record<string, string>>({});

  // Glossary
  const [terms, setTerms] = useState<GlossaryTerm[]>([]);
  const [assignments, setAssignments] = useState<GlossaryAssignment[]>([]);
  const [termId, setTermId] = useState<number | "">("");
  const [termColumn, setTermColumn] = useState<string>("");
  const canAssign = useMemo(() => Boolean(datasetId && termId), [datasetId, termId]);

  const selectedDataset = useMemo(() => datasets.find((d) => d.id === datasetId) || null, [datasets, datasetId]);
  const columns = info?.columns_list || selectedDataset?.columns || [];

  useEffect(() => {
    (async () => {
      try {
        const res = await api.get<DatasetItem[]>("/api/datasets/my-uploads");
        setDatasets(res || []);
        if (!datasetId && res?.length) {
          setDatasetId(res[0].id);
          setLastDatasetId(res[0].id);
        }
      } catch {
        // handled in per-page requests
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (queryDatasetId && queryDatasetId !== datasetId) setDatasetId(queryDatasetId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [queryDatasetId]);

  useEffect(() => {
    if (datasetId) setLastDatasetId(datasetId);
  }, [datasetId]);

  async function loadAll() {
    if (!datasetId) return;
    setError(null);
    setNotice(null);
    setLoading(true);

    try {
      // ─── Étape 1 : infos de base en parallèle ───────────────────────────────
      const [si, desc, cc, allowedRes, t, a] = await Promise.all([
        api.get<SimpleInfo>(`/api/datasets/${datasetId}/simple-info`),
        api.get<DescriptionRow[]>(`/api/datasets/${datasetId}/descriptions`).catch((e) => {
          console.warn("[DescribePage] /descriptions error:", e);
          return [] as DescriptionRow[];
        }),
        api.get<ColumnClassRow[]>(`/api/datasets/${datasetId}/column-classifications`).catch((e) => {
          console.warn("[DescribePage] /column-classifications error:", e);
          return [] as ColumnClassRow[];
        }),
        api.get<AllowedClassificationsResponse>(`/dataset/${datasetId}/allowed-classifications`).catch((e) => {
          console.warn("[DescribePage] /allowed-classifications error:", e);
          return null;
        }),
        canAssignGlossary
          ? api.get<GlossaryTerm[]>("/glossary/terms").catch((e) => {
              console.warn("[DescribePage] /glossary/terms error:", e);
              return [] as GlossaryTerm[];
            })
          : Promise.resolve([] as GlossaryTerm[]),
        canAssignGlossary
          ? api.get<GlossaryAssignment[]>(`/glossary/datasets/${datasetId}/terms`).catch((e) => {
              console.warn("[DescribePage] /glossary/datasets/.../terms error:", e);
              return [] as GlossaryAssignment[];
            })
          : Promise.resolve([] as GlossaryAssignment[]),
      ]);

      setInfo(si);

      // ─── Étape 2 : construire la map de descriptions ─────────────────────────
      // Priorité : descriptions manuelles > versions héritées > suggestions parent
      const map: Record<string, string> = {};
      const sources: Record<string, DescriptionSource> = {};

      // 2a. Descriptions déjà saisies manuellement (priorité max)
      for (const d of desc || []) {
        if (d.description?.trim()) {
          map[d.column_name] = d.description;
          sources[d.column_name] = "manual";
        }
      }

      // 2b. Héritage depuis les versions précédentes du MÊME dataset
      // On appelle séquentiellement après avoir le résultat de /descriptions
      // pour logguer clairement ce qui se passe.
      try {
        const inherited = await api.get<InheritedDescriptionsResponse>(
          `/api/datasets/${datasetId}/inherited-descriptions`
        );
        console.log("[DescribePage] inherited-descriptions:", inherited);

        let inheritedCount = 0;
        for (const version of inherited?.versions || []) {
          inheritedCount += fillMissingDescriptions(map, version.descriptions, "inherited", sources);
        }
        if (inheritedCount > 0) {
          console.log(`[DescribePage] ${inheritedCount} champs remplis depuis l'héritage de versions`);
        }
      } catch (e) {
        // L'endpoint n'existe pas encore ou dataset sans parent de version → OK
        console.warn("[DescribePage] /inherited-descriptions non disponible:", e);
      }

      // 2c. Suggestions depuis datasets liés (même projet, même schéma)
      try {
        const parentSuggestions = await api.get<ParentSuggestionsResponse>(
          `/api/datasets/${datasetId}/parent-suggestions`
        );
        console.log("[DescribePage] parent-suggestions:", parentSuggestions);

        let suggCount = 0;
        // On applique les suggestions dès qu'elles existent, même si has_parent
        // est faux. Cela évite de perdre le préremplissage quand le backend
        // renvoie des suggestions sans marquer explicitement un parent.
        for (const row of parentSuggestions?.suggestions || []) {
          if (row.description?.trim() && !map[row.column_name]) {
            map[row.column_name] = row.description;
            sources[row.column_name] = "suggestion";
            suggCount++;
          }
        }
        if (suggCount > 0) {
          console.log(`[DescribePage] ${suggCount} champs remplis depuis les suggestions parent`);
        }
      } catch (e) {
        // Pas de suggestions disponibles → OK
        console.warn("[DescribePage] /parent-suggestions non disponible:", e);
      }

      console.log("[DescribePage] map final:", map);
      console.log("[DescribePage] sources:", sources);

      setDescriptions(map);
      setDescSources(sources);

      // ─── Étape 3 : notice utilisateur si héritage détecté ───────────────────
      const inheritedCols = Object.values(sources).filter((s) => s === "inherited").length;
      const suggCols = Object.values(sources).filter((s) => s === "suggestion").length;

      if (inheritedCols > 0 || suggCols > 0) {
        const parts: string[] = [];
        if (inheritedCols > 0) parts.push(`${inheritedCols} colonne(s) héritée(s) d'une version précédente`);
        if (suggCols > 0) parts.push(`${suggCols} colonne(s) suggérée(s) depuis un dataset lié`);
        setNotice(`Pré-remplissage automatique : ${parts.join(" · ")}. Modifiez si nécessaire.`);
      }

      // ─── Étape 4 : classifications & glossaire ───────────────────────────────
      const ccMap: Record<string, string> = {};
      for (const row of cc || []) ccMap[row.column_name] = row.classification_name || "NONE";
      setColClasses(ccMap);

      setAllowed(allowedRes);
      setTerms(t || []);
      setAssignments(a || []);
      if (allowedRes?.message) setNotice((prev) => prev ? `${prev} — ${allowedRes.message}` : allowedRes.message!);

    } catch (e) {
      const err = e as ApiError;
      setError(err.bodyText || err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [datasetId]);

  function setDesc(column: string, value: string) {
    setDescriptions((prev) => ({ ...prev, [column]: value }));
    // Dès que l'utilisateur modifie, la source devient "manual"
    setDescSources((prev) => ({ ...prev, [column]: "manual" }));
  }

  function setClass(column: string, value: string) {
    setColClasses((prev) => ({ ...prev, [column]: value }));
  }

  const classificationOptions = useMemo(() => {
    const opts = ["NONE", ...(allowed?.allowed || [])];
    return Array.from(new Set(opts));
  }, [allowed]);

  async function save() {
    if (!datasetId) return;
    if (!canEdit) return;
    setError(null);
    setNotice(null);
    setSaving(true);
    try {
      const payload = {
        descriptions: columns.map((c) => ({ column_name: c, description: String(descriptions[c] || "").trim() })),
        classifications: columns.map((c) => ({
          column_name: c,
          classification_name: (colClasses[c] || "NONE") === "NONE" ? null : colClasses[c],
        })),
      };
      const res = await api.post<{ message?: string }>(`/api/datasets/${datasetId}/descriptions`, payload);
      setNotice(res?.message || "Sauvegardé.");
      await loadAll();
    } catch (e) {
      const err = e as ApiError;
      setError(err.bodyText || err.message);
    } finally {
      setSaving(false);
    }
  }

  async function addAssignment() {
    if (!datasetId || !termId) return;
    setError(null);
    setNotice(null);
    setSaving(true);
    try {
      await api.post<GlossaryAssignment>(`/glossary/datasets/${datasetId}/terms`, {
        term_id: termId,
        column_name: termColumn || null,
      });
      setTermId("");
      setTermColumn("");
      const a = await api.get<GlossaryAssignment[]>(`/glossary/datasets/${datasetId}/terms`).catch(() => []);
      setAssignments(a || []);
    } catch (e) {
      const err = e as ApiError;
      setError(err.bodyText || err.message);
    } finally {
      setSaving(false);
    }
  }

  async function removeAssignment(row: GlossaryAssignment) {
    if (!datasetId) return;
    setError(null);
    setNotice(null);
    setSaving(true);
    try {
      const col = row.column_name ? `?column_name=${encodeURIComponent(row.column_name)}` : "";
      await api.del<{ message: string }>(`/glossary/datasets/${datasetId}/terms/${row.glossary_term_id}${col}`);
      const a = await api.get<GlossaryAssignment[]>(`/glossary/datasets/${datasetId}/terms`).catch(() => []);
      setAssignments(a || []);
    } catch (e) {
      const err = e as ApiError;
      setError(err.bodyText || err.message);
    } finally {
      setSaving(false);
    }
  }

  // Badge visuel selon la source de la description
  function SourceBadge({ col }: { col: string }) {
    const src = descSources[col];
    if (!src || src === "manual") return null;
    return (
      <Chip
        size="small"
        label={src === "inherited" ? "Hérité" : "Suggestion"}
        color={src === "inherited" ? "info" : "warning"}
        variant="outlined"
        sx={{ ml: 1, fontSize: "0.7rem", height: 20 }}
      />
    );
  }

  return (
    <Box>
      <PageHeader
        title="Descriptions & Gouvernance"
        subtitle="Renseigne les descriptions, les classifications (PII/SENSITIVE), et assigne des termes de glossaire."
        right={
          <Stack direction="row" spacing={1}>
            <Button variant="outlined" onClick={() => navigate("/results")} disabled={!datasetId}>
              Voir résultats
            </Button>
            <Button
              variant="contained"
              startIcon={<SaveOutlinedIcon />}
              onClick={save}
              disabled={!datasetId || saving || loading || !canEdit}
            >
              Sauvegarder
            </Button>
          </Stack>
        }
      />

      <Paper
        elevation={0}
        sx={{
          p: 2.5,
          borderRadius: 3,
          mb: 2,
          background: "linear-gradient(135deg, rgba(30,64,175,0.08), rgba(15,118,110,0.08))"
        }}
      >
        <Typography variant="subtitle1" sx={{ mb: 0.5 }}>
          À retenir
        </Typography>
        <Typography variant="body2" color="text.secondary">
          La visibilité du dataset dit qui peut le voir dans l’application. La classification des colonnes dit si une
          colonne contient des données sensibles. Atlas reçoit ensuite ces informations pour le catalogue technique.
        </Typography>
      </Paper>

      {error ? <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert> : null}
      {notice ? <Alert severity="info" sx={{ mb: 2 }}>{notice}</Alert> : null}

      <Paper elevation={0} sx={{ p: 3, borderRadius: 3 }}>
        <Stack spacing={2.5}>
          <FormControl fullWidth>
            <InputLabel id="ds">Dataset</InputLabel>
            <Select
              labelId="ds"
              label="Dataset"
              value={datasetId}
              onChange={(e) => setDatasetId(String(e.target.value))}
            >
              {datasets.map((d) => (
                <MenuItem key={d.id} value={d.id}>
                  {d.name} ({d.project?.name || "Sans projet"}) — {d.classification} — {d.columns_count} colonnes
                </MenuItem>
              ))}
            </Select>
          </FormControl>

          {info ? (
            <Stack direction="row" spacing={1} flexWrap="wrap">
              <Chip size="small" label={`Colonnes: ${info.columns_list?.length || 0}`} variant="outlined" />
              {allowed?.dataset_classification ? (
                <Chip size="small" label={`Visibilité: ${allowed.dataset_classification}`} />
              ) : null}
            </Stack>
          ) : null}

          <Divider />

          <Tabs value={tab} onChange={(_, v) => setTab(v)} variant="scrollable" allowScrollButtonsMobile>
            <Tab value="descriptions" label="Descriptions" />
            <Tab value="classifications" label="Classifications" />
            {canAssignGlossary ? <Tab value="glossary" label="Glossaire" /> : null}
          </Tabs>

          {tab === "descriptions" ? (
            <Stack spacing={2}>
              {columns.map((c) => (
                <Box key={c}>
                  <Stack direction="row" alignItems="center" sx={{ mb: 0.5 }}>
                    <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 500 }}>
                      {c}
                    </Typography>
                    <SourceBadge col={c} />
                  </Stack>
                  <TextField
                    fullWidth
                    value={descriptions[c] ?? ""}
                    onChange={(e) => setDesc(c, e.target.value)}
                    disabled={!canEdit}
                    multiline
                    minRows={2}
                    placeholder="Décrire la colonne…"
                    // Highlight si pré-rempli automatiquement
                    sx={
                      descSources[c] && descSources[c] !== "manual"
                        ? {
                            "& .MuiOutlinedInput-root fieldset": {
                              borderColor: descSources[c] === "inherited" ? "info.main" : "warning.main",
                              borderWidth: "1.5px",
                            },
                          }
                        : undefined
                    }
                  />
                </Box>
              ))}
              {columns.length === 0 ? (
                <Typography variant="body2" color="text.secondary">
                  Aucune colonne détectée.
                </Typography>
              ) : null}
            </Stack>
          ) : null}

          {tab === "classifications" ? (
            <Stack spacing={2}>
              {columns.map((c, idx) => (
                <FormControl key={c} fullWidth>
                  <InputLabel id={`cls-${idx}`}>{c}</InputLabel>
                  <Select
                    labelId={`cls-${idx}`}
                    label={c}
                    value={colClasses[c] || "NONE"}
                    onChange={(e) => setClass(c, String(e.target.value))}
                    disabled={!canEdit}
                  >
                    {classificationOptions.map((o) => (
                      <MenuItem key={o} value={o}>
                        {o}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
              ))}
              {columns.length === 0 ? (
                <Typography variant="body2" color="text.secondary">
                  Aucune colonne détectée.
                </Typography>
              ) : null}
            </Stack>
          ) : null}

          {tab === "glossary" && canAssignGlossary ? (
            <Stack spacing={2}>
              <Typography variant="subtitle1">Assigner un terme</Typography>
              <Stack direction={{ xs: "column", md: "row" }} spacing={2} alignItems={{ md: "center" }}>
                <FormControl fullWidth>
                  <InputLabel id="term">Terme</InputLabel>
                  <Select
                    labelId="term"
                    label="Terme"
                    value={termId}
                    onChange={(e) => {
                      const v = e.target.value as any;
                      if (v === "") setTermId("");
                      else setTermId(Number(v));
                    }}
                  >
                    <MenuItem value="">
                      <em>Sélectionner…</em>
                    </MenuItem>
                    {terms.map((t) => (
                      <MenuItem key={t.id} value={t.id}>
                        {t.term} {t.glossary_name ? `— ${t.glossary_name}` : ""}{" "}
                        {t.category_name ? `(${t.category_name})` : ""}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
                <FormControl fullWidth>
                  <InputLabel id="col">Colonne (optionnel)</InputLabel>
                  <Select
                    labelId="col"
                    label="Colonne (optionnel)"
                    value={termColumn}
                    onChange={(e) => setTermColumn(String(e.target.value))}
                  >
                    <MenuItem value="">Dataset (niveau dataset)</MenuItem>
                    {columns.map((c) => (
                      <MenuItem key={c} value={c}>
                        {c}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
                <Button
                  variant="contained"
                  startIcon={<AddOutlinedIcon />}
                  onClick={addAssignment}
                  disabled={!canAssign || saving || loading || !canEdit}
                >
                  Assigner
                </Button>
              </Stack>

              <Divider />

              <Typography variant="subtitle1">Attributions existantes</Typography>
              <Stack spacing={1}>
                {(assignments || []).map((a) => (
                  <Paper key={`${a.glossary_term_id}-${a.column_name || "DATASET"}`} variant="outlined" sx={{ p: 1.5 }}>
                    <Stack direction={{ xs: "column", sm: "row" }} spacing={1} alignItems={{ sm: "center" }}>
                      <Box sx={{ flex: 1 }}>
                        <Typography variant="body2">
                          {a.term} {a.glossary_name ? `— ${a.glossary_name}` : ""}{" "}
                          {a.category_name ? `(${a.category_name})` : ""}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          Cible: {a.column_name || "Dataset"}
                        </Typography>
                      </Box>
                      <Button
                        color="error"
                        variant="outlined"
                        startIcon={<DeleteOutlineOutlinedIcon />}
                        onClick={() => removeAssignment(a)}
                        disabled={saving || loading || !canEdit}
                      >
                        Retirer
                      </Button>
                    </Stack>
                  </Paper>
                ))}
                {assignments.length === 0 ? (
                  <Typography variant="body2" color="text.secondary">
                    Aucun terme assigné pour ce dataset.
                  </Typography>
                ) : null}
              </Stack>
            </Stack>
          ) : null}
        </Stack>
      </Paper>
    </Box>
  );
}
