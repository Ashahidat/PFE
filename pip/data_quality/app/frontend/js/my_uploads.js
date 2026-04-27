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

function renderTermOptions(selectedTermIds) {
    const selected = new Set(
        (Array.isArray(selectedTermIds) ? selectedTermIds : (selectedTermIds ? [selectedTermIds] : []))
            .filter(Boolean)
            .map((id) => String(id))
    );
    const options = [];
    for (const term of glossaryTerms) {
        const label = term.category_name
            ? `${term.term} (${term.category_name})`
            : term.term;
        const value = String(term.id);
        const isSelected = selected.has(value) ? " selected" : "";
        options.push(`<option value=\"${value}\"${isSelected}>${escapeHtml(label)}</option>`);
    }
    return options.join("");
}

function formatAssignedTerms(assignments) {
    if (!assignments || !assignments.length) return "Pas de terme";
    return assignments.map((a) => a.term).filter(Boolean).join(", ") || "Pas de terme";
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
    assignmentBadge.textContent = dataset.dataset_assignments?.length
        ? `Termes: ${formatAssignedTerms(dataset.dataset_assignments)}`
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

    const descriptionEditor = document.createElement("div");
    descriptionEditor.className = "dataset-meta-editor";
    const descLabel = document.createElement("div");
    descLabel.className = "dataset-meta-label";
    descLabel.textContent = "Description du dataset:";
    const descTextarea = document.createElement("textarea");
    descTextarea.className = "dataset-meta-textarea";
    descTextarea.rows = 3;
    descTextarea.value = dataset.description || "";
    descTextarea.disabled = !dataset.can_edit;
    const descActions = document.createElement("div");
    descActions.className = "dataset-meta-actions";
    const descSaveBtn = document.createElement("button");
    descSaveBtn.type = "button";
    descSaveBtn.className = "btn-small secondary";
    descSaveBtn.textContent = "Sauvegarder";
    descSaveBtn.disabled = !dataset.can_edit;
    const descStatus = document.createElement("span");
    descStatus.className = "status-pill info dataset-meta-status";
    descStatus.textContent = "";
    descStatus.style.display = "none";
    descSaveBtn.addEventListener("click", async () => {
        await saveDatasetDescription(dataset, descTextarea, descStatus, descSaveBtn, card);
    });
    descActions.append(descSaveBtn, descStatus);
    descriptionEditor.append(descLabel, descTextarea, descActions);
    detail.appendChild(descriptionEditor);

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

    const securitySection = document.createElement("div");
    securitySection.className = "dataset-security-section";
    securitySection.innerHTML = `
        <div class="dataset-meta-label">Sécurité (Atlas)</div>
        <div class="dataset-security-row">
            <select class="dataset-security-select" data-security-select="${dataset.id}">
                <option value="RESTRICTED">RESTRICTED (département)</option>
                <option value="PUBLIC">PUBLIC (entreprise)</option>
            </select>
            <button type="button" class="btn-small" data-security-apply="${dataset.id}">Appliquer</button>
            <span class="status-pill info dataset-security-status" data-security-status="${dataset.id}" style="display:none;"></span>
        </div>
        <div class="dataset-security-columns muted" data-security-columns="${dataset.id}"></div>
    `;
    // hidden until we load details (need Atlas guid / mappings)
    securitySection.style.display = dataset.atlas_synced ? "block" : "none";
    detail.appendChild(securitySection);

    const termSection = document.createElement("div");
    termSection.className = "dataset-term-section";
    const termLabel = document.createElement("span");
    termLabel.textContent = "Terme Atlas:";
    const termSelect = document.createElement("select");
    termSelect.className = "dataset-term-select";
    termSelect.multiple = true;
    termSelect.size = 6;
    termSelect.innerHTML = renderTermOptions(dataset.dataset_assignments?.map((a) => a.term_id));
    termSelect.disabled = !dataset.can_edit;
    const termButton = document.createElement("button");
    termButton.type = "button";
    termButton.textContent = "Appliquer";
    termButton.disabled = !dataset.can_edit;
    termButton.addEventListener("click", () => updateDatasetTerms(dataset, termSelect, card));

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
        const [res, atlasColsRes, allowedRes, colClassRes] = await Promise.all([
            fetchWithAuth(`/api/datasets/${datasetId}/metadata`),
            dataset.atlas_synced ? fetchWithAuth(`/api/datasets/${datasetId}/atlas-columns`) : Promise.resolve(null),
            dataset.atlas_synced ? fetchWithAuth(`/dataset/${datasetId}/allowed-classifications`) : Promise.resolve(null),
            dataset.atlas_synced ? fetchWithAuth(`/dataset/${datasetId}/column-classifications`) : Promise.resolve(null),
        ]);
        if (!res.ok) {
            throw new Error("Impossible de charger les métadonnées");
        }
        const metadata = await res.json();

        const atlasColumns = atlasColsRes && atlasColsRes.ok ? (await atlasColsRes.json()).columns : {};
        const allowed = allowedRes && allowedRes.ok ? await allowedRes.json() : { dataset_classification: null };
        const existingColClasses = colClassRes && colClassRes.ok ? (await colClassRes.json()).columns : {};

        initSecurityControls(dataset, detailEl, canEdit, card, allowed, atlasColumns, existingColClasses);

        if (!metadata.columns.length) {
            columnsSection.innerHTML = "<p>Aucune colonne détectée.</p>";
            return;
        }
        columnsSection.innerHTML = "";
        for (const column of metadata.columns) {
            columnsSection.append(createColumnRow(dataset, column, canEdit, card, atlasColumns, existingColClasses));
        }
    } catch (error) {
        console.error(error);
        columnsSection.innerHTML = '<p class="error">Impossible de charger les colonnes.</p>';
    }
}

function createColumnRow(dataset, column, canEdit, card, atlasColumns = {}, existingColClasses = {}) {
    const row = document.createElement("div");
    row.className = "column-row";

    const label = document.createElement("div");
    label.className = "column-name";
    const labelText = document.createElement("strong");
    labelText.textContent = column.name;
    const labelMeta = document.createElement("div");
    labelMeta.className = "column-meta";
    labelMeta.textContent = column.classifications?.length
        ? formatAssignedTerms(column.classifications)
        : (column.classification?.term || "Pas de terme");
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
    termSelect.multiple = true;
    termSelect.size = 5;
    termSelect.innerHTML = renderTermOptions((column.classifications || []).map((a) => a.term_id));
    termSelect.disabled = !canEdit;

    const securitySelect = document.createElement("select");
    securitySelect.className = "column-security-select";
    securitySelect.innerHTML = `
        <option value="">Aucune</option>
        <option value="PII">PII</option>
        <option value="SENSITIVE">SENSITIVE</option>
    `;
    const existing = existingColClasses[column.name] ? existingColClasses[column.name].classification : "";
    securitySelect.value = existing || "";
    securitySelect.disabled = !canEdit || !dataset.atlas_synced;

    const saveBtn = document.createElement("button");
    saveBtn.type = "button";
    saveBtn.textContent = "Sauvegarder";
    saveBtn.disabled = !canEdit;
    saveBtn.className = "btn-small";

    const applySecBtn = document.createElement("button");
    applySecBtn.type = "button";
    applySecBtn.textContent = "Classer";
    applySecBtn.disabled = !canEdit || !dataset.atlas_synced;
    applySecBtn.className = "btn-small secondary";

    const clearSecBtn = document.createElement("button");
    clearSecBtn.type = "button";
    clearSecBtn.textContent = "Retirer";
    clearSecBtn.disabled = !canEdit || !dataset.atlas_synced;
    clearSecBtn.className = "btn-small secondary";

    const columnStatus = document.createElement("span");
    columnStatus.className = "column-status status-pill";

    const datasetId = dataset?.id;
    saveBtn.addEventListener("click", async () => {
        const termIds = Array.from(termSelect.selectedOptions || [])
            .map((opt) => opt && opt.value ? Number(opt.value) : null)
            .filter((v) => Number.isFinite(v));
        await saveColumnMetadata(datasetId, column.name, description, termIds, columnStatus, saveBtn);
    });

    applySecBtn.addEventListener("click", async () => {
        await applyColumnSecurityClassification(dataset, column.name, securitySelect.value, atlasColumns, columnStatus);
    });
    clearSecBtn.addEventListener("click", async () => {
        await removeColumnSecurityClassification(dataset, column.name, atlasColumns, columnStatus);
        securitySelect.value = "";
    });

    actions.append(termSelect, securitySelect, saveBtn, applySecBtn, clearSecBtn, columnStatus);
    row.append(label, description, actions);
    return row;
}

async function saveColumnMetadata(datasetId, columnName, descriptionEl, termIds, statusEl, button) {
    if (button) button.disabled = true;
    statusEl.textContent = "Enregistrement...";
    statusEl.className = "column-status status-pill info";

    const payload = {};
    const trimmed = (descriptionEl?.value || "").trim();
    if (trimmed.length) {
        payload.description = trimmed;
    }
    payload.glossary_term_ids = Array.isArray(termIds) ? termIds : [];

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

async function updateDatasetTerms(dataset, selectEl, card) {
    if (!dataset.can_edit) return;
    const statusEl = card.querySelector(`#dataset-status-${dataset.id}`);
    showDetailMessage(statusEl, "Mise à jour...", "info");
    const termIds = Array.from(selectEl.selectedOptions || [])
        .map((opt) => opt && opt.value ? Number(opt.value) : null)
        .filter((v) => Number.isFinite(v));
    const payload = {
        glossary_term_ids: termIds
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
        const data = await res.json();
        const assignments = data?.dataset_assignments || [];
        const assignmentBadge = card.querySelector(`[data-assignment-badge="${dataset.id}"]`);
        if (assignmentBadge) {
            assignmentBadge.textContent = assignments.length
                ? `Termes: ${formatAssignedTerms(assignments)}`
                : "Pas de terme";
        }
        const message = assignments.length
            ? "Termes mis à jour"
            : "Termes retirés";
        showDetailMessage(statusEl, message, "success");
    } catch (error) {
        console.error(error);
        showDetailMessage(statusEl, "Erreur réseau", "error");
    }
}

async function saveDatasetDescription(dataset, textareaEl, statusEl, button, card) {
    if (button) button.disabled = true;
    statusEl.style.display = "inline-flex";
    statusEl.textContent = "Enregistrement...";
    statusEl.className = "status-pill info dataset-meta-status";

    const payload = {
        description: (textareaEl?.value || "").trim()
    };

    try {
        const res = await fetchWithAuth(`/api/datasets/${dataset.id}/description`, {
            method: "PUT",
            body: JSON.stringify(payload)
        });
        if (!res.ok) {
            const err = await res.text();
            throw new Error(err);
        }
        const data = await res.json();
        statusEl.textContent = data.synced_to_atlas ? "Sauvé + Atlas" : "Sauvé (DB)";
        statusEl.className = "status-pill success dataset-meta-status";
        // Update card summary
        const summary = card.querySelector(".dataset-description");
        if (summary) {
            summary.textContent = payload.description || "Aucune description fournie.";
        }
    } catch (error) {
        console.error(error);
        statusEl.textContent = "Erreur";
        statusEl.className = "status-pill error dataset-meta-status";
    } finally {
        if (button) button.disabled = false;
        setTimeout(() => { statusEl.style.display = "none"; }, 2500);
    }
}

function initSecurityControls(dataset, detailEl, canEdit, card, allowed, atlasColumns, existingColClasses) {
    const select = detailEl.querySelector(`[data-security-select="${dataset.id}"]`);
    const applyBtn = detailEl.querySelector(`[data-security-apply="${dataset.id}"]`);
    const statusEl = detailEl.querySelector(`[data-security-status="${dataset.id}"]`);
    const colsInfo = detailEl.querySelector(`[data-security-columns="${dataset.id}"]`);
    if (!select || !applyBtn || !statusEl || !colsInfo) return;

    const current = allowed && allowed.dataset_classification ? allowed.dataset_classification : (dataset.classification || "RESTRICTED");
    select.value = current;
    select.disabled = !canEdit;
    applyBtn.disabled = !canEdit;

    const atlasColCount = atlasColumns ? Object.keys(atlasColumns).length : 0;
    const classifiedCount = existingColClasses ? Object.keys(existingColClasses).length : 0;
    colsInfo.textContent = `Colonnes Atlas: ${atlasColCount} | Colonnes classifiées: ${classifiedCount}`;

    applyBtn.addEventListener("click", async () => {
        statusEl.style.display = "inline-flex";
        statusEl.textContent = "Application...";
        statusEl.className = "status-pill info dataset-security-status";
        try {
            await applyDatasetSecurityClassification(dataset, select.value);
            statusEl.textContent = "OK";
            statusEl.className = "status-pill success dataset-security-status";
        } catch (e) {
            console.error(e);
            statusEl.textContent = "Erreur";
            statusEl.className = "status-pill error dataset-security-status";
        } finally {
            setTimeout(() => { statusEl.style.display = "none"; }, 2500);
        }
    });
}

async function applyDatasetSecurityClassification(dataset, classification) {
    const payload = {
        entity_type: "DATASET",
        entity_id: dataset.id,
        atlas_guid: dataset.atlas_guid,
        classification_name: classification,
        attributes: classification === "PUBLIC"
            ? { visibility_scope: "ENTERPRISE" }
            : { visibility_scope: "DEPARTMENT" }
    };

    const res = await fetchWithAuth(`/apply-classification`, {
        method: "POST",
        body: JSON.stringify(payload)
    });
    if (!res.ok) {
        const err = await res.text();
        throw new Error(err);
    }
}

async function applyColumnSecurityClassification(dataset, columnName, classification, atlasColumns, statusEl) {
    statusEl.textContent = "Classification...";
    statusEl.className = "column-status status-pill info";

    if (!classification) {
        statusEl.textContent = "Choisir PII/SENSITIVE";
        statusEl.className = "column-status status-pill error";
        return;
    }

    const columnGuid = atlasColumns && atlasColumns[columnName] ? atlasColumns[columnName].guid : null;
    if (!columnGuid) {
        statusEl.textContent = "GUID colonne manquant";
        statusEl.className = "column-status status-pill error";
        return;
    }

    const payload = {
        entity_type: "COLUMN",
        entity_id: dataset.id,
        atlas_guid: columnGuid,
        classification_name: classification,
        column_name: columnName,
        attributes: {}
    };

    try {
        const res = await fetchWithAuth(`/apply-classification`, {
            method: "POST",
            body: JSON.stringify(payload)
        });
        if (!res.ok) {
            const err = await res.text();
            throw new Error(err);
        }
        statusEl.textContent = "OK";
        statusEl.className = "column-status status-pill success";
    } catch (e) {
        console.error(e);
        statusEl.textContent = "Erreur";
        statusEl.className = "column-status status-pill error";
    }
}

async function removeColumnSecurityClassification(dataset, columnName, atlasColumns, statusEl) {
    statusEl.textContent = "Suppression...";
    statusEl.className = "column-status status-pill info";

    const columnGuid = atlasColumns && atlasColumns[columnName] ? atlasColumns[columnName].guid : null;
    if (!columnGuid) {
        statusEl.textContent = "GUID colonne manquant";
        statusEl.className = "column-status status-pill error";
        return;
    }

    const payload = {
        entity_type: "COLUMN",
        entity_id: dataset.id,
        atlas_guid: columnGuid,
        column_name: columnName,
        classification_names: ["PII", "SENSITIVE"]
    };

    try {
        const res = await fetchWithAuth(`/remove-classification`, {
            method: "POST",
            body: JSON.stringify(payload)
        });
        if (!res.ok) {
            const err = await res.text();
            throw new Error(err);
        }
        statusEl.textContent = "Supprimé";
        statusEl.className = "column-status status-pill success";
    } catch (e) {
        console.error(e);
        statusEl.textContent = "Erreur";
        statusEl.className = "column-status status-pill error";
    }
}

window.addEventListener("DOMContentLoaded", async () => {
    showPageMessage("Chargement...");
    await loadGlossaryTerms();
    await loadDatasets();
});
