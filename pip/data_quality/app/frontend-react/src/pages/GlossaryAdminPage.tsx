import {
  Alert,
  Box,
  Button,
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
import AddOutlinedIcon from "@mui/icons-material/AddOutlined";
import DeleteOutlineOutlinedIcon from "@mui/icons-material/DeleteOutlineOutlined";
import EditOutlinedIcon from "@mui/icons-material/EditOutlined";
import SyncOutlinedIcon from "@mui/icons-material/SyncOutlined";
import PageHeader from "../components/PageHeader";
import { useEffect, useMemo, useState } from "react";
import { api, ApiError } from "../lib/api";

type Glossary = { id: number; name: string; description?: string | null; created_at?: string | null };
type Category = { id: number; name: string; description?: string | null; glossary_id: number; glossary_name?: string | null };
type Term = {
  id: number;
  term: string;
  description?: string | null;
  glossary_id: number;
  glossary_name?: string | null;
  category_id?: number | null;
  category_name?: string | null;
};

export default function GlossaryAdminPage() {
  const [tab, setTab] = useState<"glossaries" | "categories" | "terms">("glossaries");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const [glossaries, setGlossaries] = useState<Glossary[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [terms, setTerms] = useState<Term[]>([]);

  // Create/edit forms
  const [gId, setGId] = useState<number | null>(null);
  const [gName, setGName] = useState("");
  const [gDesc, setGDesc] = useState("");

  const [cId, setCId] = useState<number | null>(null);
  const [cName, setCName] = useState("");
  const [cDesc, setCDesc] = useState("");
  const [cGlossaryId, setCGlossaryId] = useState<number | "">("");

  const [tId, setTId] = useState<number | null>(null);
  const [tTerm, setTTerm] = useState("");
  const [tDesc, setTDesc] = useState("");
  const [tGlossaryId, setTGlossaryId] = useState<number | "">("");
  const [tCategoryId, setTCategoryId] = useState<number | "">("");

  const categoryOptions = useMemo(
    () => categories.filter((c) => (tGlossaryId ? c.glossary_id === tGlossaryId : true)),
    [categories, tGlossaryId]
  );

  async function loadAll() {
    setError(null);
    setNotice(null);
    setLoading(true);
    try {
      const [gs, cs, ts] = await Promise.all([
        api.get<Glossary[]>("/glossary/glossaries"),
        api.get<Category[]>("/glossary/categories"),
        api.get<Term[]>("/glossary/terms")
      ]);
      setGlossaries(gs || []);
      setCategories(cs || []);
      setTerms(ts || []);
    } catch (e) {
      const err = e as ApiError;
      setError(err.bodyText || err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadAll();
  }, []);

  async function syncAtlas() {
    setError(null);
    setNotice(null);
    setLoading(true);
    try {
      const res = await api.post<{ message?: string }>("/glossary/sync", {});
      setNotice(res?.message || "Sync lancé.");
    } catch (e) {
      const err = e as ApiError;
      setError(err.bodyText || err.message);
    } finally {
      setLoading(false);
    }
  }

  function resetG() {
    setGId(null);
    setGName("");
    setGDesc("");
  }
  function resetC() {
    setCId(null);
    setCName("");
    setCDesc("");
    setCGlossaryId("");
  }
  function resetT() {
    setTId(null);
    setTTerm("");
    setTDesc("");
    setTGlossaryId("");
    setTCategoryId("");
  }

  async function saveGlossary() {
    setError(null);
    setNotice(null);
    setLoading(true);
    try {
      if (gId) {
        await api.put(`/glossary/glossaries/${gId}`, { name: gName, description: gDesc || null });
        setNotice("Glossaire modifié.");
      } else {
        await api.post("/glossary/glossaries", { name: gName, description: gDesc || null });
        setNotice("Glossaire créé.");
      }
      resetG();
      await loadAll();
    } catch (e) {
      const err = e as ApiError;
      setError(err.bodyText || err.message);
    } finally {
      setLoading(false);
    }
  }

  async function deleteGlossary(id: number) {
    if (!confirm("Supprimer ce glossaire ?")) return;
    setError(null);
    setNotice(null);
    setLoading(true);
    try {
      await api.del(`/glossary/glossaries/${id}`);
      setNotice("Glossaire supprimé.");
      await loadAll();
    } catch (e) {
      const err = e as ApiError;
      setError(err.bodyText || err.message);
    } finally {
      setLoading(false);
    }
  }

  async function saveCategory() {
    if (!cGlossaryId) {
      setError("Choisis un glossaire.");
      return;
    }
    setError(null);
    setNotice(null);
    setLoading(true);
    try {
      const body = { name: cName, description: cDesc || null, glossary_id: cGlossaryId };
      if (cId) {
        await api.put(`/glossary/categories/${cId}`, body);
        setNotice("Catégorie modifiée.");
      } else {
        await api.post("/glossary/categories", body);
        setNotice("Catégorie créée.");
      }
      resetC();
      await loadAll();
    } catch (e) {
      const err = e as ApiError;
      setError(err.bodyText || err.message);
    } finally {
      setLoading(false);
    }
  }

  async function deleteCategory(id: number) {
    if (!confirm("Supprimer cette catégorie ?")) return;
    setError(null);
    setNotice(null);
    setLoading(true);
    try {
      await api.del(`/glossary/categories/${id}`);
      setNotice("Catégorie supprimée.");
      await loadAll();
    } catch (e) {
      const err = e as ApiError;
      setError(err.bodyText || err.message);
    } finally {
      setLoading(false);
    }
  }

  async function saveTerm() {
    if (!tGlossaryId) {
      setError("Choisis un glossaire.");
      return;
    }
    setError(null);
    setNotice(null);
    setLoading(true);
    try {
      const body = {
        term: tTerm,
        description: tDesc || null,
        glossary_id: tGlossaryId,
        category_id: tCategoryId ? tCategoryId : null
      };
      if (tId) {
        await api.put(`/glossary/terms/${tId}`, body);
        setNotice("Terme modifié.");
      } else {
        await api.post("/glossary/terms", body);
        setNotice("Terme créé.");
      }
      resetT();
      await loadAll();
    } catch (e) {
      const err = e as ApiError;
      setError(err.bodyText || err.message);
    } finally {
      setLoading(false);
    }
  }

  async function deleteTerm(id: number) {
    if (!confirm("Supprimer ce terme ?")) return;
    setError(null);
    setNotice(null);
    setLoading(true);
    try {
      await api.del(`/glossary/terms/${id}`);
      setNotice("Terme supprimé.");
      await loadAll();
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
        title="Administration glossaire"
        subtitle="Créer/modifier/supprimer glossaires, catégories et termes (rôles ADMIN / ADMIN_GLOSSAIRE)."
        right={
          <Button startIcon={<SyncOutlinedIcon />} onClick={syncAtlas} variant="outlined" disabled={loading}>
            Sync Atlas
          </Button>
        }
      />

      {error ? <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert> : null}
      {notice ? <Alert severity="info" sx={{ mb: 2 }}>{notice}</Alert> : null}

      <Paper elevation={0} sx={{ p: 3, borderRadius: 3 }}>
        <Stack spacing={2.5}>
          <Tabs value={tab} onChange={(_, v) => setTab(v)} variant="scrollable" allowScrollButtonsMobile>
            <Tab value="glossaries" label="Glossaires" />
            <Tab value="categories" label="Catégories" />
            <Tab value="terms" label="Termes" />
          </Tabs>

          {tab === "glossaries" ? (
            <Stack spacing={2}>
              <Typography variant="subtitle1">{gId ? "Modifier glossaire" : "Créer glossaire"}</Typography>
              <Stack direction={{ xs: "column", md: "row" }} spacing={2}>
                <TextField label="Nom" fullWidth value={gName} onChange={(e) => setGName(e.target.value)} />
                <TextField
                  label="Description"
                  fullWidth
                  value={gDesc}
                  onChange={(e) => setGDesc(e.target.value)}
                />
                <Button
                  variant="contained"
                  startIcon={<AddOutlinedIcon />}
                  disabled={loading || gName.trim().length < 2}
                  onClick={saveGlossary}
                >
                  {gId ? "Enregistrer" : "Créer"}
                </Button>
                {gId ? (
                  <Button variant="outlined" disabled={loading} onClick={resetG}>
                    Annuler
                  </Button>
                ) : null}
              </Stack>

              <Divider />

              <Stack spacing={1}>
                {(glossaries || []).map((g) => (
                  <Paper key={g.id} variant="outlined" sx={{ p: 1.5 }}>
                    <Stack direction={{ xs: "column", sm: "row" }} spacing={1} alignItems={{ sm: "center" }}>
                      <Box sx={{ flex: 1 }}>
                        <Typography variant="body2">{g.name}</Typography>
                        <Typography variant="caption" color="text.secondary">
                          {g.description || "—"}
                        </Typography>
                      </Box>
                      <Button
                        variant="outlined"
                        startIcon={<EditOutlinedIcon />}
                        disabled={loading}
                        onClick={() => {
                          setGId(g.id);
                          setGName(g.name);
                          setGDesc(g.description || "");
                        }}
                      >
                        Modifier
                      </Button>
                      <Button
                        color="error"
                        variant="outlined"
                        startIcon={<DeleteOutlineOutlinedIcon />}
                        disabled={loading}
                        onClick={() => deleteGlossary(g.id)}
                      >
                        Supprimer
                      </Button>
                    </Stack>
                  </Paper>
                ))}
              </Stack>
            </Stack>
          ) : null}

          {tab === "categories" ? (
            <Stack spacing={2}>
              <Typography variant="subtitle1">{cId ? "Modifier catégorie" : "Créer catégorie"}</Typography>
              <Stack direction={{ xs: "column", md: "row" }} spacing={2} alignItems={{ md: "center" }}>
                <FormControl fullWidth>
                  <InputLabel id="cat-g">Glossaire</InputLabel>
                  <Select
                    labelId="cat-g"
                    label="Glossaire"
                    value={cGlossaryId}
                    onChange={(e) => setCGlossaryId(Number(e.target.value))}
                  >
                    <MenuItem value="">
                      <em>Sélectionner…</em>
                    </MenuItem>
                    {glossaries.map((g) => (
                      <MenuItem key={g.id} value={g.id}>
                        {g.name}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
                <TextField label="Nom" fullWidth value={cName} onChange={(e) => setCName(e.target.value)} />
                <TextField
                  label="Description"
                  fullWidth
                  value={cDesc}
                  onChange={(e) => setCDesc(e.target.value)}
                />
                <Button
                  variant="contained"
                  startIcon={<AddOutlinedIcon />}
                  disabled={loading || cName.trim().length < 2}
                  onClick={saveCategory}
                >
                  {cId ? "Enregistrer" : "Créer"}
                </Button>
                {cId ? (
                  <Button variant="outlined" disabled={loading} onClick={resetC}>
                    Annuler
                  </Button>
                ) : null}
              </Stack>

              <Divider />

              <Stack spacing={1}>
                {(categories || []).map((c) => (
                  <Paper key={c.id} variant="outlined" sx={{ p: 1.5 }}>
                    <Stack direction={{ xs: "column", sm: "row" }} spacing={1} alignItems={{ sm: "center" }}>
                      <Box sx={{ flex: 1 }}>
                        <Typography variant="body2">
                          {c.name}{" "}
                          <Typography component="span" variant="caption" color="text.secondary">
                            — {c.glossary_name || `glossary_id=${c.glossary_id}`}
                          </Typography>
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          {c.description || "—"}
                        </Typography>
                      </Box>
                      <Button
                        variant="outlined"
                        startIcon={<EditOutlinedIcon />}
                        disabled={loading}
                        onClick={() => {
                          setCId(c.id);
                          setCGlossaryId(c.glossary_id);
                          setCName(c.name);
                          setCDesc(c.description || "");
                        }}
                      >
                        Modifier
                      </Button>
                      <Button
                        color="error"
                        variant="outlined"
                        startIcon={<DeleteOutlineOutlinedIcon />}
                        disabled={loading}
                        onClick={() => deleteCategory(c.id)}
                      >
                        Supprimer
                      </Button>
                    </Stack>
                  </Paper>
                ))}
              </Stack>
            </Stack>
          ) : null}

          {tab === "terms" ? (
            <Stack spacing={2}>
              <Typography variant="subtitle1">{tId ? "Modifier terme" : "Créer terme"}</Typography>
              <Stack direction={{ xs: "column", md: "row" }} spacing={2} alignItems={{ md: "center" }}>
                <FormControl fullWidth>
                  <InputLabel id="term-g">Glossaire</InputLabel>
                  <Select
                    labelId="term-g"
                    label="Glossaire"
                    value={tGlossaryId}
                    onChange={(e) => {
                      const v = e.target.value as any;
                      if (v === "") setTGlossaryId("");
                      else setTGlossaryId(Number(v));
                      setTCategoryId("");
                    }}
                  >
                    <MenuItem value="">
                      <em>Sélectionner…</em>
                    </MenuItem>
                    {glossaries.map((g) => (
                      <MenuItem key={g.id} value={g.id}>
                        {g.name}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
                <FormControl fullWidth>
                  <InputLabel id="term-c">Catégorie (optionnel)</InputLabel>
                  <Select
                    labelId="term-c"
                    label="Catégorie (optionnel)"
                    value={tCategoryId}
                    onChange={(e) => {
                      const v = e.target.value as any;
                      if (v === "") setTCategoryId("");
                      else setTCategoryId(Number(v));
                    }}
                    disabled={!tGlossaryId}
                  >
                    <MenuItem value="">
                      <em>Aucune</em>
                    </MenuItem>
                    {categoryOptions.map((c) => (
                      <MenuItem key={c.id} value={c.id}>
                        {c.name}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
                <TextField label="Terme" fullWidth value={tTerm} onChange={(e) => setTTerm(e.target.value)} />
                <TextField label="Description" fullWidth value={tDesc} onChange={(e) => setTDesc(e.target.value)} />
                <Button
                  variant="contained"
                  startIcon={<AddOutlinedIcon />}
                  disabled={loading || tTerm.trim().length < 2}
                  onClick={saveTerm}
                >
                  {tId ? "Enregistrer" : "Créer"}
                </Button>
                {tId ? (
                  <Button variant="outlined" disabled={loading} onClick={resetT}>
                    Annuler
                  </Button>
                ) : null}
              </Stack>

              <Divider />

              <Stack spacing={1}>
                {(terms || []).map((t) => (
                  <Paper key={t.id} variant="outlined" sx={{ p: 1.5 }}>
                    <Stack direction={{ xs: "column", sm: "row" }} spacing={1} alignItems={{ sm: "center" }}>
                      <Box sx={{ flex: 1 }}>
                        <Typography variant="body2">
                          {t.term}{" "}
                          <Typography component="span" variant="caption" color="text.secondary">
                            — {t.glossary_name || `glossary_id=${t.glossary_id}`}{" "}
                            {t.category_name ? `· ${t.category_name}` : ""}
                          </Typography>
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          {t.description || "—"}
                        </Typography>
                      </Box>
                      <Button
                        variant="outlined"
                        startIcon={<EditOutlinedIcon />}
                        disabled={loading}
                        onClick={() => {
                          setTId(t.id);
                          setTGlossaryId(t.glossary_id);
                          setTCategoryId(t.category_id || "");
                          setTTerm(t.term);
                          setTDesc(t.description || "");
                        }}
                      >
                        Modifier
                      </Button>
                      <Button
                        color="error"
                        variant="outlined"
                        startIcon={<DeleteOutlineOutlinedIcon />}
                        disabled={loading}
                        onClick={() => deleteTerm(t.id)}
                      >
                        Supprimer
                      </Button>
                    </Stack>
                  </Paper>
                ))}
              </Stack>
            </Stack>
          ) : null}
        </Stack>
      </Paper>
    </Box>
  );
}
