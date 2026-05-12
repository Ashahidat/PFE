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
import { useLocation } from "react-router-dom";
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

function useQuery() {
  const { search } = useLocation();
  return useMemo(() => new URLSearchParams(search), [search]);
}

export default function DescribePage() {
  const q = useQuery();
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
  const [allowed, setAllowed] = useState<AllowedClassificationsResponse | null>(null);
  const [colClasses, setColClasses] = useState<Record<string, string>>({});

  // Glossary
  const [terms, setTerms] = useState<GlossaryTerm[]>([]);
  const [assignments, setAssignments] = useState<GlossaryAssignment[]>([]);
  const [termId, setTermId] = useState<number | "">("");
  const [termColumn, setTermColumn] = useState<string>(""); // empty => dataset-level
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
      const [si, desc, cc, allowedRes, t, a] = await Promise.all([
        api.get<SimpleInfo>(`/api/datasets/${datasetId}/simple-info`),
        api.get<DescriptionRow[]>(`/api/datasets/${datasetId}/descriptions`).catch(() => []),
        api.get<ColumnClassRow[]>(`/api/datasets/${datasetId}/column-classifications`).catch(() => []),
        api.get<AllowedClassificationsResponse>(`/dataset/${datasetId}/allowed-classifications`).catch(() => null),
        canAssignGlossary ? api.get<GlossaryTerm[]>("/glossary/terms").catch(() => []) : Promise.resolve([] as GlossaryTerm[]),
        canAssignGlossary
          ? api.get<GlossaryAssignment[]>(`/glossary/datasets/${datasetId}/terms`).catch(() => [])
          : Promise.resolve([] as GlossaryAssignment[])
      ]);

      setInfo(si);
      const map: Record<string, string> = {};
      for (const d of desc || []) map[d.column_name] = d.description || "";
      setDescriptions(map);

      const ccMap: Record<string, string> = {};
      for (const row of cc || []) ccMap[row.column_name] = row.classification_name || "NONE";
      setColClasses(ccMap);

      setAllowed(allowedRes);
      setTerms(t || []);
      setAssignments(a || []);
      if (allowedRes?.message) setNotice(allowedRes.message);
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
          classification_name: (colClasses[c] || "NONE") === "NONE" ? null : colClasses[c]
        }))
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
        column_name: termColumn || null
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

  return (
    <Box>
      <PageHeader
        title="Descriptions & Gouvernance"
        subtitle="Renseigne les descriptions, les classifications (PII/SENSITIVE), et assigne des termes de glossaire."
        right={
          <Button
            variant="contained"
            startIcon={<SaveOutlinedIcon />}
            onClick={save}
            disabled={!datasetId || saving || loading || !canEdit}
          >
            Sauvegarder
          </Button>
        }
      />

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
                <TextField
                  key={c}
                  label={c}
                  value={descriptions[c] ?? ""}
                  onChange={(e) => setDesc(c, e.target.value)}
                  disabled={!canEdit}
                  multiline
                  minRows={2}
                  placeholder="Décrire la colonne…"
                />
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
