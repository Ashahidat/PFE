const API_URL = "http://localhost:8000";

// ================= DEBUG TOKEN =================
console.log("🔍 Vérification token au chargement...");
const token = localStorage.getItem("access_token");
console.log("🔑 Token dans localStorage:", token ? `${token.substring(0, 20)}...` : "AUCUN TOKEN");
if (!token) {
    window.location.href = "index.html";
}

let uploadGlossaries = [];
let uploadCategories = [];
let uploadTerms = [];

function escapeHtml(str) {
    if (!str) return "";
    return str.replace(/[&<>]/g, (m) => {
        if (m === "&") return "&amp;";
        if (m === "<") return "&lt;";
        if (m === ">") return "&gt;";
        return m;
    });
}

function setUploadGlossaryStatus(message = "", type = "info") {
    const status = document.getElementById("uploadGlossaryStatus");
    if (!status) return;
    status.textContent = message;
    if (!message) {
        status.style.color = "#555";
        return;
    }
    status.style.color = type === "error" ? "#dc3545" : type === "success" ? "#28a745" : "#555";
}

async function loadUploadGlossaries() {
    try {
        const res = await fetch(`${API_URL}/glossary/glossaries`, {
            headers: { Authorization: `Bearer ${token}` },
        });
        if (!res.ok) throw new Error("Impossible de charger les glossaires");
        uploadGlossaries = await res.json();
    } catch (err) {
        console.warn("Impossible de charger les glossaires", err);
        uploadGlossaries = [];
    }
    const select = document.getElementById("uploadGlossarySelect");
    if (!select) return;
    const options = uploadGlossaries
        .map((glossary) => `<option value="${glossary.id}">${escapeHtml(glossary.name)}</option>`)
        .join("");
    select.innerHTML =
        "<option value=''>Sélectionnez un glossaire (optionnel)</option>" + options;
    select.disabled = uploadGlossaries.length === 0;
    const defaultGlossaryId = uploadGlossaries[0]?.id || "";
    if (defaultGlossaryId) {
        select.value = defaultGlossaryId;
        await refreshUploadCategories(defaultGlossaryId);
    } else {
        await refreshUploadCategories("");
    }
}

async function loadUploadTerms() {
    try {
        const res = await fetch(`${API_URL}/glossary/terms`, {
            headers: { Authorization: `Bearer ${token}` },
        });
        if (res.ok) {
            uploadTerms = await res.json();
        } else {
            uploadTerms = [];
        }
    } catch (err) {
        console.warn("Impossible de charger les termes", err);
        uploadTerms = [];
    }
    refreshUploadTermOptions();
}

async function refreshUploadCategories(glossaryId) {
    const select = document.getElementById("uploadCategorySelect");
    if (!select) return;
    if (!glossaryId) {
        select.innerHTML = "<option value=''>Choisissez un glossaire</option>";
        select.disabled = true;
        refreshUploadTermOptions("");
        return;
    }
    try {
        const res = await fetch(`${API_URL}/glossary/categories?glossary_id=${glossaryId}`, {
            headers: { Authorization: `Bearer ${token}` },
        });
        if (!res.ok) throw new Error("Impossible de charger les catégories");
        uploadCategories = await res.json();
    } catch (err) {
        console.warn("Impossible de charger les catégories", err);
        uploadCategories = [];
    }
    if (!uploadCategories.length) {
        select.innerHTML = "<option value=''>Aucune catégorie disponible</option>";
        select.disabled = true;
    } else {
        select.innerHTML =
            "<option value=''>Toutes catégories</option>" +
            uploadCategories
                .map((category) => `<option value="${category.id}">${escapeHtml(category.name)}</option>`)
                .join("");
        select.disabled = false;
    }
    refreshUploadTermOptions("");
}

function refreshUploadTermOptions(categoryId = "") {
    const glossarySelect = document.getElementById("uploadGlossarySelect");
    const select = document.getElementById("uploadTermSelect");
    if (!select || !glossarySelect) return;
    const glossaryId = glossarySelect.value;
    if (!glossaryId) {
        select.innerHTML = "<option value=''>Sélectionnez un glossaire</option>";
        select.disabled = true;
        return;
    }
    let filtered = uploadTerms.filter((term) => String(term.glossary_id) === String(glossaryId));
    if (categoryId) {
        filtered = filtered.filter((term) => String(term.category_id) === String(categoryId));
    }
    if (!filtered.length) {
        select.innerHTML = "<option value=''>Aucun terme disponible</option>";
        select.disabled = true;
        return;
    }
    select.disabled = false;
    select.innerHTML = filtered
        .map(
            (term) =>
                `<option value="${term.id}">${escapeHtml(term.term)}${
                    term.category_name ? ` (${escapeHtml(term.category_name)})` : ""
                }</option>`
        )
        .join("");
}

async function assignTermToDatasetAfterUpload(datasetId) {
    const termSelect = document.getElementById("uploadTermSelect");
    if (!termSelect) return false;
    const termIds = Array.from(termSelect.selectedOptions || [])
        .map((opt) => opt && opt.value ? Number(opt.value) : null)
        .filter((v) => Number.isFinite(v));
    if (!termIds.length) {
        setUploadGlossaryStatus("", "info");
        return false;
    }
    setUploadGlossaryStatus("Assignation glossaire en cours...", "info");
    try {
        const res = await fetch(`${API_URL}/api/datasets/${datasetId}/classification`, {
            method: "PUT",
            headers: {
                "Content-Type": "application/json",
                Authorization: `Bearer ${token}`,
            },
            body: JSON.stringify({ glossary_term_ids: termIds }),
        });
        if (!res.ok) {
            const error = await res.json().catch(() => ({}));
            setUploadGlossaryStatus(`❌ ${error.detail || "Impossible d'assigner ce terme"}`, "error");
            return false;
        }
        setUploadGlossaryStatus("✅ Terme(s) assigné(s) pour ce dataset", "success");
        return true;
    } catch (err) {
        console.error("Erreur assignation glossaire:", err);
        setUploadGlossaryStatus("❌ Échec de l'assignation", "error");
        return false;
    }
}

// UX: allow multi-select without Ctrl/Cmd (toggle on click)
function enableToggleMultiSelect(selectId) {
    const select = document.getElementById(selectId);
    if (!select) return;
    if (!select.multiple) return;
    // Avoid double-binding if this script is loaded twice.
    if (select.dataset.toggleMultiSelect === "1") return;
    select.dataset.toggleMultiSelect = "1";

    select.addEventListener("mousedown", (event) => {
        const option = event.target && event.target.tagName === "OPTION" ? event.target : null;
        if (!option) return;

        // Keep native behavior for disabled/select-all cases.
        if (select.disabled || option.disabled) return;

        event.preventDefault();

        const previousScrollTop = select.scrollTop;
        option.selected = !option.selected;
        // Keep focus so keyboard navigation still works.
        select.focus();
        select.scrollTop = previousScrollTop;

        // Ensure code listening to change reacts.
        select.dispatchEvent(new Event("change", { bubbles: true }));
    });
}

// ================= AFFICHAGE PROJET =================
document.addEventListener("DOMContentLoaded", async () => {
    const projectName = localStorage.getItem("current_project_name");
    if (projectName) {
        document.getElementById("currentProjectName").textContent = projectName;
    } else {
        window.location.href = "projects.html"; // Rediriger si pas de projet
    }

    await Promise.all([loadUploadGlossaries(), loadUploadTerms()]);

    const glossarySelect = document.getElementById("uploadGlossarySelect");
    if (glossarySelect) {
        glossarySelect.addEventListener("change", async (event) => {
            setUploadGlossaryStatus("", "info");
            await refreshUploadCategories(event.target.value);
        });
    }

    const categorySelect = document.getElementById("uploadCategorySelect");
    if (categorySelect) {
        categorySelect.addEventListener("change", (event) => {
            setUploadGlossaryStatus("", "info");
            refreshUploadTermOptions(event.target.value);
        });
    }

    enableToggleMultiSelect("uploadTermSelect");
});

// ================= UPLOAD CSV =================
document.getElementById("uploadBtn").addEventListener("click", async () => {
    const file = document.getElementById("csvFile").files[0];
    const projectId = localStorage.getItem("current_project_id");
    const description = document.getElementById("description").value; // ✅ Récupérer description
    const datasetVisibilityEl = document.getElementById("datasetVisibility");
    const datasetVisibility = datasetVisibilityEl ? datasetVisibilityEl.value : "";
    const statusDiv = document.getElementById("uploadStatus");

    console.log("🟡 Début processus upload...");
    console.log("📄 Fichier sélectionné:", file ? file.name : "Aucun");
    console.log("📁 Projet sélectionné:", projectId);
    console.log("📝 Description:", description);
    console.log("🔒 Visibilité dataset:", datasetVisibility || "(défaut projet)");

    // 🔴 Vérifications
    if (!file) {
        console.log("❌ Aucun fichier sélectionné");
        return alert("Choisissez un fichier CSV");
    }

    if (!projectId) {
        console.log("❌ Aucun projet sélectionné");
        return alert("Sélectionnez un projet d'abord");
    }

    statusDiv.innerText = "En cours d'exécution...";
    statusDiv.classList.remove("hidden");

    // ================= FormData =================
    const formData = new FormData();
    formData.append("file", file);
    formData.append("project_id", projectId);
    formData.append("description", description); // ✅ Ajouter description
    if (datasetVisibility) {
        formData.append("dataset_visibility", datasetVisibility);
    }

    try {
        const token = localStorage.getItem("access_token");
        console.log("🔑 Token récupéré:", token ? `${token.substring(0, 20)}...` : "Token manquant");

        console.log("🔄 Envoi requête POST /upload...");

        const res = await fetch(`${API_URL}/upload`, {
            method: "POST",
            body: formData,
            headers: {
                "Authorization": `Bearer ${token}`
            }
        });

        console.log(`📊 Réponse HTTP: ${res.status} ${res.statusText}`);

        const data = await res.json();
        console.log("📨 Données reçues:", data);

        if (!res.ok) {
            console.error("❌ Erreur serveur:", data);
            throw new Error(data.detail || "Erreur upload");
        }

        // ✔ Sauvegarde dataset_id
        localStorage.setItem("last_uploaded_dataset_id", data.dataset_id);

        if (data.columns) {
            window.columns = data.columns;
            console.log("✅ Upload réussi, colonnes:", data.columns);

            statusDiv.innerText = "Fichier uploadé avec succès !";

            // ✔ Redirection
            console.log("🔀 Redirection vers preview.html");
            await assignTermToDatasetAfterUpload(data.dataset_id);
            window.location.href = "preview.html";

        } else {
            console.warn("⚠️ Colonnes manquantes dans la réponse");
            statusDiv.innerText = "Erreur : colonnes introuvables";
        }

    } catch (err) {
        console.error("💥 Erreur complète:", err);
        statusDiv.innerText = "Erreur upload CSV";
    }
});
