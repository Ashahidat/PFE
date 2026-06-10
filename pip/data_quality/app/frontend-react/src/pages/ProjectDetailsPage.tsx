import {
  Alert,
  Box,
  Button,
  Chip,
  Divider,
  Grid,
  LinearProgress,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography
} from "@mui/material";
import ExpandMoreOutlinedIcon from "@mui/icons-material/ExpandMoreOutlined";
import OpenInNewOutlinedIcon from "@mui/icons-material/OpenInNewOutlined";
import DescriptionOutlinedIcon from "@mui/icons-material/DescriptionOutlined";
import StorageOutlinedIcon from "@mui/icons-material/StorageOutlined";
import VisibilityOutlinedIcon from "@mui/icons-material/VisibilityOutlined";
import AssignmentOutlinedIcon from "@mui/icons-material/AssignmentOutlined";
import { Accordion, AccordionDetails, AccordionSummary } from "@mui/material";
import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import PageHeader from "../components/PageHeader";
import AtlasUiLinkButton from "../components/AtlasUiLinkButton";
import { api, ApiError } from "../lib/api";
import { setLastDatasetId } from "../lib/storage";

type Project = {
  id: string;
  name: string;
  description?: string | null;
  owner_employee_id: string;
  visibility: "PUBLIC" | "DEPARTMENT";
  created_at: string;
  datasets_count: number;
  grafana_links?: {
    folder?: { url?: string | null } | null;
  } | null;
};

type ProjectDataset = {
  id: string;
  name: string;
  description?: string | null;
  uploaded_by?: string | null;
  classification: string;
  columns: string[];
  columns_count: number;
  created_at?: string | null;
  atlas_guid?: string | null;
  atlas_synced: boolean;
  can_edit: boolean;
};

type AssignmentInfo = {
  term_id: number;
  term: string;
  glossary_id?: number | null;
  glossary_name?: string | null;
  category_id?: number | null;
  category_name?: string | null;
  assigned_by?: string | null;
  assigned_at?: string | null;
};

type ColumnMetadata = {
  name: string;
  description?: string | null;
  classification?: AssignmentInfo | null;
  classifications: AssignmentInfo[];
};

type DatasetMetadata = {
  id: string;
  name: string;
  file_name: string;
  hash: string;
  description?: string | null;
  classification: string;
  dataset_assignment?: AssignmentInfo | null;
  dataset_assignments: AssignmentInfo[];
  columns: ColumnMetadata[];
  can_edit: boolean;
};

type PreviewRow = Record<string, string | number | boolean | null>;

function fmtDate(value?: string | null) {
  if (!value) return "—";
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return value;
  return dt.toLocaleString("fr-FR");
}

function assignmentLabel(a: AssignmentInfo) {
  return [a.term, a.glossary_name, a.category_name].filter(Boolean).join(" · ");
}

export default function ProjectDetailsPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const [project, setProject] = useState<Project | null>(null);
  const [datasets, setDatasets] = useState<ProjectDataset[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | false>(false);
  const [metadataById, setMetadataById] = useState<Record<string, DatasetMetadata>>({});
  const [previewById, setPreviewById] = useState<Record<string, PreviewRow[]>>({});
  const [detailLoading, setDetailLoading] = useState<Record<string, boolean>>({});
  const [detailError, setDetailError] = useState<Record<string, string | null>>({});

  const grafanaUrl = project?.grafana_links?.folder?.url || null;

  async function loadProject() {
    if (!projectId) return;
    setError(null);
    setLoading(true);
    setProject(null);
    setDatasets([]);
    setExpandedId(false);
    setMetadataById({});
    setPreviewById({});
    setDetailLoading({});
    setDetailError({});
    try {
      const [projectRes, datasetsRes] = await Promise.all([
        api.get<Project>(`/projects/${projectId}`),
        api.get<ProjectDataset[]>(`/projects/${projectId}/datasets`)
      ]);
      setProject(projectRes);
      setDatasets(datasetsRes || []);
      if (datasetsRes?.length) {
        setExpandedId(datasetsRes[0].id);
      }
    } catch (e) {
      const err = e as ApiError;
      setError(err.bodyText || err.message);
    } finally {
      setLoading(false);
    }
  }

  async function loadDatasetDetails(datasetId: string) {
    if (!datasetId || metadataById[datasetId] || detailLoading[datasetId]) return;
    setDetailLoading((prev) => ({ ...prev, [datasetId]: true }));
    setDetailError((prev) => ({ ...prev, [datasetId]: null }));
    try {
      const [metadata, preview] = await Promise.all([
        api.get<DatasetMetadata>(`/api/datasets/${datasetId}/metadata`),
        api.get<PreviewRow[]>(`/preview/${datasetId}?n=5`)
      ]);
      setMetadataById((prev) => ({ ...prev, [datasetId]: metadata }));
      setPreviewById((prev) => ({ ...prev, [datasetId]: preview || [] }));
    } catch (e) {
      const err = e as ApiError;
      setDetailError((prev) => ({ ...prev, [datasetId]: err.bodyText || err.message }));
    } finally {
      setDetailLoading((prev) => ({ ...prev, [datasetId]: false }));
    }
  }

  useEffect(() => {
    void loadProject();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  useEffect(() => {
    if (expandedId) void loadDatasetDetails(expandedId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [expandedId]);

  const overview = useMemo(() => {
    const total = datasets.length;
    const synced = datasets.filter((d) => d.atlas_synced).length;
    const editable = datasets.filter((d) => d.can_edit).length;
    return { total, synced, editable };
  }, [datasets]);

  return (
    <Box>
      <PageHeader
        crumbs={[{ label: "Projets", to: "/projects" }, { label: project?.name || "Détails" }]}
        title={project?.name || "Détails projet"}
        subtitle="Vue détaillée du projet, de ses datasets, de leurs colonnes et de leur gouvernance."
        right={<AtlasUiLinkButton variant="outlined" />}
      />

      {error ? <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert> : null}
      {loading ? <LinearProgress sx={{ mb: 2 }} /> : null}

      {project ? (
        <Paper elevation={0} sx={{ p: 3, borderRadius: 3, mb: 3 }}>
          <Stack spacing={2}>
            <Stack direction={{ xs: "column", md: "row" }} justifyContent="space-between" gap={2}>
              <Box>
                <Typography variant="h6">{project.name}</Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                  {project.description || "Aucune description renseignée."}
                </Typography>
              </Box>
              <Stack direction="row" spacing={1} flexWrap="wrap">
                <Chip
                  label={project.visibility}
                  color={project.visibility === "PUBLIC" ? "success" : "default"}
                  variant={project.visibility === "PUBLIC" ? "filled" : "outlined"}
                />
                <Chip label={`${overview.total} dataset(s)`} variant="outlined" icon={<StorageOutlinedIcon />} />
                <Chip label={`${overview.synced} Atlas sync`} variant="outlined" icon={<VisibilityOutlinedIcon />} />
                <Chip label={`${overview.editable} éditable(s)`} variant="outlined" icon={<AssignmentOutlinedIcon />} />
              </Stack>
            </Stack>

            <Grid container spacing={2}>
              <Grid item xs={12} md={4}>
                <Paper variant="outlined" sx={{ p: 2, height: "100%" }}>
                  <Typography variant="caption" color="text.secondary">
                    Propriétaire
                  </Typography>
                  <Typography variant="body1" sx={{ fontWeight: 600 }}>
                    {project.owner_employee_id}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    Créé le {fmtDate(project.created_at)}
                  </Typography>
                </Paper>
              </Grid>
              <Grid item xs={12} md={4}>
                <Paper variant="outlined" sx={{ p: 2, height: "100%" }}>
                  <Typography variant="caption" color="text.secondary">
                    Datasets visibles
                  </Typography>
                  <Typography variant="body1" sx={{ fontWeight: 600 }}>
                    {overview.total}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    {datasets.filter((d) => d.description).length} avec description
                  </Typography>
                </Paper>
              </Grid>
              <Grid item xs={12} md={4}>
                <Paper variant="outlined" sx={{ p: 2, height: "100%" }}>
                  <Typography variant="caption" color="text.secondary">
                    Accès rapides
                  </Typography>
                  <Stack direction="row" spacing={1} sx={{ mt: 1 }} flexWrap="wrap">
                    <Button
                      variant="outlined"
                      onClick={() => navigate(`/upload?project_id=${encodeURIComponent(project.id)}`)}
                    >
                      Uploader ici
                    </Button>
                    <AtlasUiLinkButton variant="outlined" />
                    {grafanaUrl ? (
                      <Button href={grafanaUrl} target="_blank" rel="noopener" variant="outlined" endIcon={<OpenInNewOutlinedIcon />}>
                        Grafana
                      </Button>
                    ) : null}
                  </Stack>
                </Paper>
              </Grid>
            </Grid>
          </Stack>
        </Paper>
      ) : null}

      <Stack spacing={2}>
        {datasets.map((dataset) => {
          const metadata = metadataById[dataset.id];
          const preview = previewById[dataset.id] || [];
          const detailErr = detailError[dataset.id];
          const isLoadingDetail = detailLoading[dataset.id];
          const expanded = expandedId === dataset.id;
          const describedColumns = metadata?.columns.filter((c) => Boolean(c.description?.trim())).length || 0;
          const classifiedColumns = metadata?.columns.filter((c) => (c.classifications || []).length > 0).length || 0;
          const datasetAssignments = metadata?.dataset_assignments?.length || 0;
          const sampleKeys = preview[0] ? Object.keys(preview[0]).slice(0, 8) : [];

          return (
            <Accordion
              key={dataset.id}
              expanded={expanded}
              onChange={(_, nextExpanded) => {
                setExpandedId(nextExpanded ? dataset.id : false);
              }}
              sx={{ borderRadius: 3, overflow: "hidden" }}
            >
              <AccordionSummary expandIcon={<ExpandMoreOutlinedIcon />}>
                <Box sx={{ width: "100%" }}>
                  <Stack direction={{ xs: "column", md: "row" }} justifyContent="space-between" gap={1}>
                    <Box sx={{ minWidth: 0 }}>
                      <Typography variant="subtitle1" noWrap sx={{ fontWeight: 700 }}>
                        {dataset.name}
                      </Typography>
                      <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                        {dataset.description || "Aucune description dataset."}
                      </Typography>
                    </Box>
                    <Stack direction="row" spacing={1} flexWrap="wrap" alignItems="center">
                      <Chip size="small" label={`${dataset.columns_count} colonnes`} />
                      <Chip size="small" label={dataset.classification} variant="outlined" />
                      <Chip
                        size="small"
                        label={dataset.atlas_synced ? "Atlas synced" : "Atlas pending"}
                        color={dataset.atlas_synced ? "success" : "warning"}
                        variant={dataset.atlas_synced ? "filled" : "outlined"}
                      />
                    </Stack>
                  </Stack>
                </Box>
              </AccordionSummary>
              <AccordionDetails>
                {detailErr ? <Alert severity="error" sx={{ mb: 2 }}>{detailErr}</Alert> : null}
                {isLoadingDetail ? <LinearProgress sx={{ mb: 2 }} /> : null}

                {metadata ? (
                  <Stack spacing={2}>
                    <Stack direction={{ xs: "column", md: "row" }} spacing={1} justifyContent="space-between">
                      <Stack direction="row" spacing={1} flexWrap="wrap">
                        <Chip label={`Colonnes: ${metadata.columns.length}`} icon={<StorageOutlinedIcon />} />
                        <Chip label={`Descriptions: ${describedColumns}/${metadata.columns.length || 1}`} icon={<DescriptionOutlinedIcon />} />
                        <Chip label={`Classifiées: ${classifiedColumns}/${metadata.columns.length || 1}`} icon={<VisibilityOutlinedIcon />} />
                        <Chip label={`Assignations dataset: ${datasetAssignments}`} icon={<AssignmentOutlinedIcon />} />
                      </Stack>
                      <Stack direction="row" spacing={1} flexWrap="wrap">
                        <Button
                          variant="outlined"
                          size="small"
                          onClick={() => {
                            setLastDatasetId(dataset.id);
                            navigate(`/describe?dataset_id=${encodeURIComponent(dataset.id)}`);
                          }}
                        >
                          Ouvrir la gouvernance
                        </Button>
                        <Button
                          variant="outlined"
                          size="small"
                          onClick={() => navigate(`/upload?project_id=${encodeURIComponent(project?.id || "")}`)}
                        >
                          Uploader
                        </Button>
                      </Stack>
                    </Stack>

                    <Grid container spacing={2}>
                      <Grid item xs={12} md={6}>
                        <Paper variant="outlined" sx={{ p: 2, height: "100%" }}>
                          <Typography variant="subtitle2" sx={{ mb: 1 }}>
                            Profilage rapide
                          </Typography>
                          <Stack spacing={1}>
                            <Typography variant="body2" color="text.secondary">
                              Fichier: {metadata.file_name}
                            </Typography>
                            <Typography variant="body2" color="text.secondary">
                              Hash: {metadata.hash}
                            </Typography>
                            <Typography variant="body2" color="text.secondary">
                              Classification dataset: {metadata.classification}
                            </Typography>
                            <Typography variant="body2" color="text.secondary">
                              Description: {metadata.description || "—"}
                            </Typography>
                            <Typography variant="body2" color="text.secondary">
                              Taille de l'aperçu: {preview.length} ligne(s)
                            </Typography>
                          </Stack>
                          <Divider sx={{ my: 2 }} />
                          <Stack spacing={1} direction="row" flexWrap="wrap">
                            {metadata.dataset_assignment ? (
                              <Chip size="small" label={`Dataset: ${assignmentLabel(metadata.dataset_assignment)}`} />
                            ) : (
                              <Chip size="small" label="Aucune assignation dataset" variant="outlined" />
                            )}
                            {(metadata.dataset_assignments || []).map((a) => (
                              <Chip key={a.term_id} size="small" label={assignmentLabel(a)} variant="outlined" />
                            ))}
                          </Stack>
                        </Paper>
                      </Grid>
                      <Grid item xs={12} md={6}>
                        <Paper variant="outlined" sx={{ p: 2, height: "100%" }}>
                          <Typography variant="subtitle2" sx={{ mb: 1 }}>
                            Colonnes
                          </Typography>
                          <Stack spacing={1.2}>
                            {metadata.columns.map((col) => (
                              <Paper key={col.name} variant="outlined" sx={{ p: 1.5 }}>
                                <Stack spacing={0.5}>
                                  <Stack direction="row" justifyContent="space-between" gap={1}>
                                    <Typography variant="body2" sx={{ fontWeight: 700 }}>
                                      {col.name}
                                    </Typography>
                                    <Stack direction="row" spacing={0.5} flexWrap="wrap" justifyContent="flex-end">
                                      {(col.classifications || []).length ? (
                                        <Chip size="small" label={`${col.classifications.length} classification(s)`} />
                                      ) : (
                                        <Chip size="small" label="Sans classification" variant="outlined" />
                                      )}
                                    </Stack>
                                  </Stack>
                                  <Typography variant="caption" color="text.secondary">
                                    {col.description || "Aucune description"}
                                  </Typography>
                                  {col.classifications?.length ? (
                                    <Stack direction="row" spacing={0.5} flexWrap="wrap">
                                      {col.classifications.map((a) => (
                                        <Chip key={`${col.name}-${a.term_id}`} size="small" variant="outlined" label={assignmentLabel(a)} />
                                      ))}
                                    </Stack>
                                  ) : null}
                                </Stack>
                              </Paper>
                            ))}
                            {metadata.columns.length === 0 ? (
                              <Typography variant="body2" color="text.secondary">
                                Aucune colonne disponible.
                              </Typography>
                            ) : null}
                          </Stack>
                        </Paper>
                      </Grid>
                    </Grid>

                    <Paper variant="outlined" sx={{ p: 2 }}>
                      <Typography variant="subtitle2" sx={{ mb: 1 }}>
                        Aperçu des données
                      </Typography>
                      {preview.length ? (
                        <TableContainer sx={{ maxHeight: 360 }}>
                          <Table stickyHeader size="small">
                            <TableHead>
                              <TableRow>
                                {sampleKeys.map((key) => (
                                  <TableCell key={key}>{key}</TableCell>
                                ))}
                                {Object.keys(preview[0] || {}).length > sampleKeys.length ? (
                                  <TableCell>...</TableCell>
                                ) : null}
                              </TableRow>
                            </TableHead>
                            <TableBody>
                              {preview.map((row, idx) => (
                                <TableRow key={idx} hover>
                                  {sampleKeys.map((key) => (
                                    <TableCell key={key}>{String(row[key] ?? "—")}</TableCell>
                                  ))}
                                  {Object.keys(preview[0] || {}).length > sampleKeys.length ? (
                                    <TableCell>…</TableCell>
                                  ) : null}
                                </TableRow>
                              ))}
                            </TableBody>
                          </Table>
                        </TableContainer>
                      ) : (
                        <Typography variant="body2" color="text.secondary">
                          Aucun aperçu disponible.
                        </Typography>
                      )}
                    </Paper>
                  </Stack>
                ) : null}
              </AccordionDetails>
            </Accordion>
          );
        })}

        {!loading && datasets.length === 0 && !error ? (
          <Alert severity="info">Aucun dataset visible dans ce projet.</Alert>
        ) : null}
      </Stack>
    </Box>
  );
}
