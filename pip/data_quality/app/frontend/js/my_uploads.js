const API_URL = "http://localhost:8000";
const token = localStorage.getItem("access_token");

const uploadsListEl = document.getElementById("uploadsList");
const uploadsStatusEl = document.getElementById("uploadsStatus");
const glossaryTerms = [];

if (!token) {
    window.location.href = "index.html";
}

async function fetchWithAuth(path, options = {}) {
    const headers = {
        Authorization: `Bearer ${token}`,
        ...(options.headers || {})
    };

    if (options.body && !Object.keys(headers).some(key => key.toLowerCase() === "content-type")) {
        headers["Content-Type"] = "application/json";
    }

    const response = await fetch(`${API_URL}${path}`, {
        ...options,
        headers
    });

    if (response.status === 401) {
        localStorage.clear();
        window.location.href = "index.html";
    }

    return response;
}

function escapeHtml(value) {
    if (!value) return "";
    return value.replace(/[&<>"']/g, (char) => {
        return {
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            '"': "&quot;",
            "'": "&#39;"
        }[char];
    });
}

function renderTermOptions(selectedTermId) {
    const normalized = selectedTermId ? String(selectedTermId) : "";
    const options = ["<option value=\"\">— Aucun terme</option>"];
    for (const term of glossaryTerms) {
        const label = term.category_name
            ? `${term.term} (${term.category_name})`
            : term.term;
        const value = String(term.id);
        const selected = normalized && normalized === value ? " selected" : "";
        options.push(`<option value=\"${value}\"${selected}>${escapeHtml(label)}</option>`);
    }
    return options.join("");
}

function showPageMessage(message, type = "info") {
    if (!uploadsStatusEl) return;
    uploadsStatusEl.textContent = message;
    uploadsStatusEl.className = message ? `status-pill ${type}` : "status-pill";
}

function showDetailMessage(container, message, type = "info") {
    if (!container) return;
    container.textContent = message;
    container.className = `dataset-status-message status-pill ${type}`;
}

function markDatasetSynced(card, dataset, synced) {
    const statusBadge = card.querySelector(`[data-atlas-status="${dataset.id}"]`);
    if (statusBadge) {
        statusBadge.textContent = synced ? "Synchronisé Atlas" : "À synchroniser";
        statusBadge.className = `badge ${synced ? "badge-success" : "badge-warning"}`;
    }
    const warning = card.querySelector(`[data-atlas-warning="${dataset.id}"]`);
    if (warning) {
        warning.style.display = synced ? "none" : "block";
    }
}

async function loadGlossaryTerms() {
    try {
        const res = await fetchWithAuth("/glossary/terms");
        if (!res.ok) throw new Error("Impossible de charger les termes");
        const data = await res.json();
        data.sort((a, b) => (a.term || "").localeCompare(b.term || ""));
        glossaryTerms.length = 0;
        glossaryTerms.push(...data);
    } catch (error) {
        console.error("Chargement des termes impossible", error);
    }
}

async function loadDatasets() {
    if (!uploadsListEl) return;
    uploadsListEl.innerHTML = "<p>Chargement...</p>";
    try {
        const res = await fetchWithAuth("/api/datasets/my-uploads");
        if (!res.ok) {
            throw new Error("Erreur lors de la récupération des datasets");
        }
        const datasets = await res.json();
        renderDatasets(datasets);
        if (!datasets.length) {
            showPageMessage("Vous n'avez pas encore d'upload.", "info");
        } else {
            showPageMessage("");
        }
    } catch (error) {
        console.error(error);
        uploadsListEl.innerHTML = '<p class="error">Impossible de charger vos uploads.</p>';
        showPageMessage("Une erreur est survenue lors du chargement.", "error");
    }
}

function renderDatasets(datasets) {
    uploadsListEl.innerHTML = "";
    if (!datasets.length) {
        uploadsListEl.innerHTML = '<p>Aucun dataset à afficher.</p>';
        return;
    }

    const grouped = groupDatasetsByProject(datasets);
    for (const group of grouped) {
        uploadsListEl.appendChild(createProjectSection(group));
    }
}

function groupDatasetsByProject(datasets) {
    const groups = [];
    const index = {};

    for (const dataset of datasets) {
        const projectId = dataset.project?.id || "__unassigned__";
        if (!index[projectId]) {
            index[projectId] = {
                projectName: dataset.project?.name || "(Projet non attribué)",
                visibility: dataset.project?.visibility || "DEPARTMENT",
                datasets: []
            };
            groups.push(index[projectId]);
        }
        index[projectId].datasets.push(dataset);
    }

    return groups;
}

function createProjectSection(group) {
    const section = document.createElement("section");
    section.className = "project-group";

    const heading = document.createElement("div");
    heading.className = "project-heading";
    heading.innerHTML = `
        <div>
            <strong>${escapeHtml(group.projectName)}</strong>
            <span class="badge badge-${group.visibility === "PUBLIC" ? "success" : "warning"}">
                ${group.visibility}
            </span>
            <small>${group.datasets.length} dataset${group.datasets.length > 1 ? "s" : ""}</small>
        </div>
    `;

    const datasetContainer = document.createElement("div");
    datasetContainer.className = "project-datasets";
    for (const dataset of group.datasets) {
        datasetContainer.appendChild(createDatasetCard(dataset));
    }

    section.append(heading, datasetContainer);
    return section;
}

function formatDate(value) {
    if (!value) return "";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return date.toLocaleString("fr-FR", { year: "numeric", month: "short", day: "numeric" });
}

function createDatasetCard(dataset) {
    const card = document.createElement("div");
    card.className = "dataset-card";

    const header = document.createElement("div");
    header.className = "dataset-header";

    const infoBlock = document.createElement("div");
    const title = document.createElement("strong");
    title.textContent = dataset.name;
    infoBlock.appendChild(title);

    const infoMeta = document.createElement("div");
    infoMeta.className = "dataset-meta";
    if (dataset.project) {
        const projectBadge = document.createElement("span");
        projectBadge.className = "badge";
        projectBadge.textContent = `Projet ${dataset.project.name} (${dataset.project.visibility})`;
        infoMeta.appendChild(projectBadge);
    }
    const columnsBadge = document.createElement("span");
    columnsBadge.className = "badge";
    columnsBadge.textContent = `${dataset.columns_count} colonne${dataset.columns_count > 1 ? "s" : ""}`;
    infoMeta.appendChild(columnsBadge);
    if (dataset.created_at) {
        const createdBadge = document.createElement("span");
        createdBadge.className = "badge";
        createdBadge.textContent = `Créé le ${formatDate(dataset.created_at)}`;
        infoMeta.appendChild(createdBadge);
    }

    const description = document.createElement("p");
    description.className = "dataset-description";
    description.textContent = dataset.description || "Aucune description fournie.";

    const classificationRow = document.createElement("div");
    classificationRow.className = "dataset-meta";
    const visibilityBadge = document.createElement("span");
    visibilityBadge.className = "badge";
    visibilityBadge.textContent = dataset.classification;
    classificationRow.appendChild(visibilityBadge);

    const atlasStatus = document.createElement("span");
    atlasStatus.dataset.atlasStatus = dataset.id;
    atlasStatus.className = `badge ${dataset.atlas_synced ? "badge-success" : "badge-warning"}`;
    atlasStatus.textContent = dataset.atlas_synced ? "Synchronisé Atlas" : "À synchroniser";
    classificationRow.appendChild(atlasStatus);

    const assignmentBadge = document.createElement("span");
    assignmentBadge.className = "badge assignment-badge";
    assignmentBadge.dataset.assignmentBadge = dataset.id;
    assignmentBadge.textContent = dataset.dataset_assignment
        ? `Terme: ${dataset.dataset_assignment.term}`
        : "Pas de terme";
    classificationRow.appendChild(assignmentBadge);

    infoBlock.appendChild(infoMeta);
    infoBlock.appendChild(classificationRow);
    header.appendChild(infoBlock);

    const toggleBtn = document.createElement("button");
    toggleBtn.type = "button";
    toggleBtn.className = "btn-link";
    toggleBtn.textContent = "Voir les détails";
    header.appendChild(toggleBtn);
    card.appendChild(header);
    card.appendChild(description);

    const detail = document.createElement("div");
    detail.className = "dataset-details hidden";
    detail.dataset.loaded = "false";

    let warning;
    if (!dataset.atlas_synced) {
        warning = document.createElement("p");
        warning.className = "atlas-warning";
        warning.dataset.atlasWarning = dataset.id;
        warning.textContent = "Ce dataset doit être synchronisé avec Atlas avant d'être modifiable.";
        detail.appendChild(warning);
    }

    const statusMessage = document.createElement("div");
    statusMessage.id = `dataset-status-${dataset.id}`;
    statusMessage.className = "dataset-status-message";
    detail.appendChild(statusMessage);

    const termSection = document.createElement("div");
    termSection.className = "dataset-term-section";
    const termLabel = document.createElement("span");
    termLabel.textContent = "Terme Atlas:";
    const termSelect = document.createElement("select");
    termSelect.className = "dataset-term-select";
    termSelect.innerHTML = renderTermOptions(dataset.dataset_assignment?.term_id);
    termSelect.disabled = !dataset.can_edit;
    const termButton = document.createElement("button");
    termButton.type = "button";
    termButton.textContent = "Appliquer";
    termButton.disabled = !dataset.can_edit;
    termButton.addEventListener("click", () => updateDatasetTerm(dataset, termSelect, card));

    termSection.append(termLabel, termSelect, termButton);
    detail.appendChild(termSection);

    const columnsSection = document.createElement("div");
    columnsSection.id = `columns-${dataset.id}`;
    columnsSection.className = "columns-section";
    columnsSection.innerHTML = "<p>Ouvrez les détails pour charger les colonnes.</p>";
    detail.appendChild(columnsSection);
    card.appendChild(detail);

    markDatasetSynced(card, dataset, dataset.atlas_synced);

    toggleBtn.addEventListener("click", async () => {
        const hidden = detail.classList.toggle("hidden");
        toggleBtn.textContent = hidden ? "Voir les détails" : "Masquer";
        if (!hidden && detail.dataset.loaded === "false") {
            detail.dataset.loaded = "true";
            await loadDatasetMetadata(dataset, detail, dataset.can_edit, card);
        }
    });

    return card;
}

async function loadDatasetMetadata(dataset, detailEl, canEdit, card) {
    const datasetId = dataset.id;
    const columnsSection = detailEl.querySelector(`#columns-${datasetId}`);
    if (!columnsSection) return;
    columnsSection.innerHTML = "<p>Chargement des colonnes...</p>";
    try {
        const res = await fetchWithAuth(`/api/datasets/${datasetId}/metadata`);
        if (!res.ok) {
            throw new Error("Impossible de charger les métadonnées");
        }
        const metadata = await res.json();
        if (!metadata.columns.length) {
            columnsSection.innerHTML = "<p>Aucune colonne détectée.</p>";
            return;
        }
        columnsSection.innerHTML = "";
    for (const column of metadata.columns) {
            columnsSection.append(createColumnRow(dataset, column, canEdit, card));
        }
    } catch (error) {
        console.error(error);
        columnsSection.innerHTML = '<p class="error">Impossible de charger les colonnes.</p>';
    }
}

function createColumnRow(dataset, column, canEdit, card) {
    const row = document.createElement("div");
    row.className = "column-row";

    const label = document.createElement("div");
    label.className = "column-name";
    const labelText = document.createElement("strong");
    labelText.textContent = column.name;
    const labelMeta = document.createElement("div");
    labelMeta.className = "column-meta";
    labelMeta.textContent = column.classification?.term || "Pas de terme";
    label.append(labelText, labelMeta);

    const description = document.createElement("textarea");
    description.className = "column-description";
    description.rows = 3;
    description.value = column.description || "";
    description.disabled = !canEdit;

    const actions = document.createElement("div");
    actions.className = "column-actions";
    const termSelect = document.createElement("select");
    termSelect.className = "column-term-select";
    termSelect.innerHTML = renderTermOptions(column.classification?.term_id);
    termSelect.disabled = !canEdit;
    const saveBtn = document.createElement("button");
    saveBtn.type = "button";
    saveBtn.textContent = "Sauvegarder";
    saveBtn.disabled = !canEdit;
    saveBtn.className = "btn-small";
    const columnStatus = document.createElement("span");
    columnStatus.className = "column-status status-pill";

    const datasetId = dataset?.id;
    saveBtn.addEventListener("click", async () => {
        await saveColumnMetadata(datasetId, column.name, description, termSelect.value, columnStatus, saveBtn);
    });

    actions.append(termSelect, saveBtn, columnStatus);
    row.append(label, description, actions);
    return row;
}

async function saveColumnMetadata(datasetId, columnName, descriptionEl, termValue, statusEl, button) {
    if (button) button.disabled = true;
    statusEl.textContent = "Enregistrement...";
    statusEl.className = "column-status status-pill info";

    const payload = {};
    const trimmed = (descriptionEl?.value || "").trim();
    if (trimmed.length) {
        payload.description = trimmed;
    }
    payload.glossary_term_id = termValue ? Number(termValue) : null;

    try {
        const res = await fetchWithAuth(`/api/datasets/${datasetId}/columns/${encodeURIComponent(columnName)}`, {
            method: "PUT",
            body: JSON.stringify(payload)
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: "Erreur inconnue" }));
            statusEl.textContent = err.detail || "Erreur";
            statusEl.className = "column-status status-pill error";
            return;
        }
        statusEl.textContent = "Mis à jour";
        statusEl.className = "column-status status-pill success";
    } catch (error) {
        console.error(error);
        statusEl.textContent = "Erreur réseau";
        statusEl.className = "column-status status-pill error";
    } finally {
        if (button) button.disabled = false;
    }
}

async function updateDatasetTerm(dataset, selectEl, card) {
    if (!dataset.can_edit) return;
    const statusEl = card.querySelector(`#dataset-status-${dataset.id}`);
    showDetailMessage(statusEl, "Mise à jour...", "info");
    const payload = {
        glossary_term_id: selectEl.value ? Number(selectEl.value) : null
    };
    try {
        const res = await fetchWithAuth(`/api/datasets/${dataset.id}/classification`, {
            method: "PUT",
            body: JSON.stringify(payload)
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: "Erreur inconnue" }));
            showDetailMessage(statusEl, err.detail || "Erreur", "error");
            return;
        }
        const assignment = await res.json();
        const termLabel = assignment?.term || "Pas de terme";
        const assignmentBadge = card.querySelector(`[data-assignment-badge="${dataset.id}"]`);
        if (assignmentBadge) {
            assignmentBadge.textContent = assignment?.term ? `Terme: ${assignment.term}` : "Pas de terme";
        }
        const message = assignment?.term ? `Terme mis à jour: ${assignment.term}` : "Terme retiré";
        showDetailMessage(statusEl, message, "success");
    } catch (error) {
        console.error(error);
        showDetailMessage(statusEl, "Erreur réseau", "error");
    }
}

window.addEventListener("DOMContentLoaded", async () => {
    showPageMessage("Chargement...");
    await loadGlossaryTerms();
    await loadDatasets();
});
