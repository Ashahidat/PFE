import {
  Alert,
  Box,
  Button,
  Chip,
  Divider,
  FormControl,
  FormControlLabel,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Stack,
  Switch,
  TextField,
  Typography
} from "@mui/material";
import AddOutlinedIcon from "@mui/icons-material/AddOutlined";
import PlayCircleOutlinedIcon from "@mui/icons-material/PlayCircleOutlined";
import DeleteOutlineOutlinedIcon from "@mui/icons-material/DeleteOutlineOutlined";
import PageHeader from "../components/PageHeader";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError } from "../lib/api";
import { getLastDatasetId, setLastDagRunId, setLastDatasetId } from "../lib/storage";

type DatasetItem = {
  id: string;
  name: string;
  classification: "PUBLIC" | "DEPARTMENT";
  columns: string[];
  columns_count: number;
  atlas_synced: boolean;
  project?: { id: string; name: string; visibility: string } | null;
};

type DeequRule =
  | { id: string; type: "completeness"; column: string; threshold: number }
  | { id: string; type: "min"; column: string; threshold: number }
  | { id: string; type: "max"; column: string; threshold: number }
  | { id: string; type: "allowed_values"; column: string; values: string[] }
  | { id: string; type: "non_negative"; column: string }
  | { id: string; type: "positive"; column: string }
  | { id: string; type: "min_length"; column: string; threshold: number }
  | { id: string; type: "max_length"; column: string; threshold: number };

function uid() {
  return Math.random().toString(16).slice(2) + Date.now().toString(16);
}

export default function RunTestsPage() {
  const navigate = useNavigate();
  const [datasets, setDatasets] = useState<DatasetItem[]>([]);
  const [datasetId, setDatasetId] = useState<string>(getLastDatasetId() || "");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Duplicates
  const [dupSensitive, setDupSensitive] = useState<string[]>([]);
  const [dupFullRow, setDupFullRow] = useState(false);

  // Great Expectations selections (backend expects {email:[...], phone:[...], postal_code:[...]})
  const [geEmail, setGeEmail] = useState<string[]>([]);
  const [gePhone, setGePhone] = useState<string[]>([]);
  const [gePostal, setGePostal] = useState<string[]>([]);

  // Deequ
  const [deequ, setDeequ] = useState<DeequRule[]>([]);

  const selected = useMemo(() => datasets.find((d) => d.id === datasetId) || null, [datasets, datasetId]);
  const columns = selected?.columns || [];

  useEffect(() => {
    (async () => {
      try {
        const res = await api.get<DatasetItem[]>("/api/datasets/my-uploads");
        setDatasets(res || []);
        if (!datasetId && res?.length) {
          setDatasetId(res[0].id);
          setLastDatasetId(res[0].id);
        }
      } catch (e) {
        const err = e as ApiError;
        setError(err.bodyText || err.message);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (datasetId) setLastDatasetId(datasetId);
  }, [datasetId]);

  const canRun = useMemo(() => Boolean(datasetId), [datasetId]);

  function addRule(type: DeequRule["type"]) {
    if (type === "allowed_values") {
      setDeequ((prev) => [...prev, { id: uid(), type, column: "", values: [] }]);
    } else if (type === "non_negative" || type === "positive") {
      setDeequ((prev) => [...prev, { id: uid(), type, column: "" } as DeequRule]);
    } else {
      setDeequ((prev) => [
        ...prev,
        {
          id: uid(),
          type,
          column: "",
          threshold: type === "completeness" ? 1 : type === "min_length" ? 1 : 0
        } as DeequRule
      ]);
    }
  }

  function removeRule(id: string) {
    setDeequ((prev) => prev.filter((r) => r.id !== id));
  }

  async function run() {
    if (!datasetId) return;
    setError(null);
    setSuccess(null);
    setLoading(true);
    try {
      const payload = {
        dataset_id: datasetId,
        rules: {
          duplicates: { sensitive: dupSensitive, full_row: dupFullRow },
          ge: {
            email: geEmail,
            phone: gePhone,
            postal_code: gePostal
          },
          deequ: deequ.map((r) => {
            if (r.type === "allowed_values") {
              return { type: r.type, column: r.column, values: r.values };
            }
            if (r.type === "non_negative" || r.type === "positive") {
              return { type: r.type, column: r.column };
            }
            return { type: r.type, column: r.column, threshold: (r as any).threshold };
          })
        }
      };
      const res = await api.post<{ message: string; dag_run_id: string }>("/run-dag-v2", payload);
      setLastDagRunId(res.dag_run_id);
      setSuccess(`DAG lancé: ${res.dag_run_id}`);
      navigate("/results");
    } catch (e) {
      const err = e as ApiError;
      setError(err.bodyText || err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <Box>
      <PageHeader
        title="Valider la qualité"
        subtitle="Choisis un dataset, configure les règles, puis déclenche Airflow."
      />
      {error ? <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert> : null}
      {success ? <Alert severity="success" sx={{ mb: 2 }}>{success}</Alert> : null}

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

          {selected ? (
            <Stack direction="row" spacing={1} flexWrap="wrap">
              <Chip size="small" label={`Visibilité: ${selected.classification}`} />
              <Chip size="small" label={`Colonnes: ${selected.columns_count}`} variant="outlined" />
              <Chip size="small" label={`Atlas: ${selected.atlas_synced ? "synced" : "not synced"}`} variant="outlined" />
            </Stack>
          ) : null}

          <Divider />

          <Typography variant="subtitle1">Doublons</Typography>
          <Stack spacing={1}>
            <FormControl fullWidth>
              <InputLabel id="dup-sensitive">Colonnes sensibles (unicité)</InputLabel>
              <Select
                labelId="dup-sensitive"
                multiple
                value={dupSensitive}
                label="Colonnes sensibles (unicité)"
                onChange={(e) => setDupSensitive(e.target.value as string[])}
                renderValue={(selected) => (selected as string[]).join(", ")}
              >
                {columns.map((c) => (
                  <MenuItem key={c} value={c}>
                    {c}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <FormControlLabel
              control={<Switch checked={dupFullRow} onChange={(e) => setDupFullRow(e.target.checked)} />}
              label="Détecter les doublons sur ligne entière"
            />
          </Stack>

          <Divider />

          <Typography variant="subtitle1">Great Expectations (formats)</Typography>
          <Stack spacing={1}>
            <FormControl fullWidth>
              <InputLabel id="re-email">Email</InputLabel>
              <Select
                labelId="re-email"
                multiple
                value={geEmail}
                label="Email"
                onChange={(e) => setGeEmail(e.target.value as string[])}
                renderValue={(selected) => (selected as string[]).join(", ")}
              >
                {columns.map((c) => (
                  <MenuItem key={c} value={c}>
                    {c}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <FormControl fullWidth>
              <InputLabel id="re-phone">Téléphone</InputLabel>
              <Select
                labelId="re-phone"
                multiple
                value={gePhone}
                label="Téléphone"
                onChange={(e) => setGePhone(e.target.value as string[])}
                renderValue={(selected) => (selected as string[]).join(", ")}
              >
                {columns.map((c) => (
                  <MenuItem key={c} value={c}>
                    {c}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <FormControl fullWidth>
              <InputLabel id="re-postal">Code postal</InputLabel>
              <Select
                labelId="re-postal"
                multiple
                value={gePostal}
                label="Code postal"
                onChange={(e) => setGePostal(e.target.value as string[])}
                renderValue={(selected) => (selected as string[]).join(", ")}
              >
                {columns.map((c) => (
                  <MenuItem key={c} value={c}>
                    {c}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Stack>

          <Divider />

          <Stack direction="row" alignItems="center" justifyContent="space-between">
            <Typography variant="subtitle1">Deequ (contraintes)</Typography>
            <Stack direction="row" spacing={1}>
              <Button size="small" variant="outlined" startIcon={<AddOutlinedIcon />} onClick={() => addRule("completeness")}>
                Complétude
              </Button>
              <Button size="small" variant="outlined" startIcon={<AddOutlinedIcon />} onClick={() => addRule("min")}>
                Min
              </Button>
              <Button size="small" variant="outlined" startIcon={<AddOutlinedIcon />} onClick={() => addRule("max")}>
                Max
              </Button>
              <Button size="small" variant="outlined" startIcon={<AddOutlinedIcon />} onClick={() => addRule("allowed_values")}>
                Valeurs
              </Button>
              <Button size="small" variant="outlined" startIcon={<AddOutlinedIcon />} onClick={() => addRule("non_negative")}>
                {"\u2265 0"}
              </Button>
              <Button size="small" variant="outlined" startIcon={<AddOutlinedIcon />} onClick={() => addRule("positive")}>
                {"\u003e 0"}
              </Button>
              <Button size="small" variant="outlined" startIcon={<AddOutlinedIcon />} onClick={() => addRule("min_length")}>
                Longueur min
              </Button>
              <Button size="small" variant="outlined" startIcon={<AddOutlinedIcon />} onClick={() => addRule("max_length")}>
                Longueur max
              </Button>
            </Stack>
          </Stack>

          <Stack spacing={1.5}>
            {deequ.length === 0 ? (
              <Typography variant="body2" color="text.secondary">
                Aucune contrainte Deequ.
              </Typography>
            ) : null}
            {deequ.map((r) => (
              <Paper key={r.id} elevation={0} sx={{ p: 2, borderRadius: 2, bgcolor: "background.default" }}>
                <Stack spacing={1}>
                  <Stack direction="row" alignItems="center" justifyContent="space-between" gap={1}>
                    <Typography variant="subtitle2">{r.type}</Typography>
                    <Button
                      size="small"
                      color="inherit"
                      startIcon={<DeleteOutlineOutlinedIcon />}
                      onClick={() => removeRule(r.id)}
                    >
                      Supprimer
                    </Button>
                  </Stack>
                  <FormControl fullWidth>
                    <InputLabel id={`col-${r.id}`}>Colonne</InputLabel>
                    <Select
                      labelId={`col-${r.id}`}
                      label="Colonne"
                      value={r.column}
                      onChange={(e) =>
                        setDeequ((prev) => prev.map((x) => (x.id === r.id ? ({ ...x, column: String(e.target.value) } as any) : x)))
                      }
                    >
                      {columns.map((c) => (
                        <MenuItem key={c} value={c}>
                          {c}
                        </MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                  {r.type === "allowed_values" ? (
                    <TextField
                      label="Valeurs autorisées (séparées par des virgules)"
                      value={r.values.join(", ")}
                      onChange={(e) =>
                        setDeequ((prev) =>
                          prev.map((x) =>
                            x.id === r.id
                              ? ({
                                  ...x,
                                  values: e.target.value
                                    .split(",")
                                    .map((v) => v.trim())
                                    .filter(Boolean)
                                } as any)
                              : x
                          )
                        )
                      }
                    />
                  ) : r.type === "non_negative" || r.type === "positive" ? null : (
                    <TextField
                      type="number"
                      label={r.type === "completeness" ? "Seuil (0..1)" : r.type.includes("length") ? "Seuil longueur" : "Seuil"}
                      value={(r as any).threshold}
                      onChange={(e) =>
                        setDeequ((prev) =>
                          prev.map((x) => (x.id === r.id ? ({ ...x, threshold: Number(e.target.value) } as any) : x))
                        )
                      }
                    />
                  )}
                </Stack>
              </Paper>
            ))}
          </Stack>

          <Divider />

          <Box>
            <Button
              variant="contained"
              startIcon={<PlayCircleOutlinedIcon />}
              onClick={run}
              disabled={!canRun || loading}
            >
              Lancer les validations
            </Button>
          </Box>
        </Stack>
      </Paper>
    </Box>
  );
}
