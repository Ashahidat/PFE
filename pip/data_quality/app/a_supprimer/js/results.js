const API_URL = window.API_URL || window.location.origin;

const POLL_INTERVAL_MS = 4000;
const MAX_ATTEMPTS = 80;

function getAuthToken() {
    return localStorage.getItem("access_token");
}

function getDagRunId() {
    return localStorage.getItem("last_dag_run_id");
}

function humanizeRuleType(ruleType) {
    if (!ruleType) return "Test";
    const rt = String(ruleType).trim();
    if (rt.startsWith("regex_")) {
        const kind = rt.replace(/^regex_/, "");
        const map = { email: "Email", phone: "Téléphone", postal: "Code postal", alphanumeric: "Alphanumérique" };
        return `Format (${map[kind] || kind})`;
    }
    if (rt.toLowerCase().includes("doublon")) return "Doublons";
    if (rt.toLowerCase().includes("deequ")) return "Qualité (Deequ)";
    return rt.replace(/_/g, " ");
}

function normalizeStatus(status) {
    const s = String(status || "").trim().toLowerCase();
    if (["réussi", "pass", "success"].includes(s)) return "success";
    if (["échoué", "fail", "failed"].includes(s)) return "failed";
    if (["ignoré", "skipped"].includes(s)) return "skipped";
    return "unknown";
}

function formatRatio(ratio) {
    if (ratio === undefined || ratio === null) return null;
    const r = String(ratio).trim();
    return r.length ? r : null;
}

function escapeHtml(unsafe) {
    return String(unsafe)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

async function fetchJson(url, token) {
    const res = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
    if (!res.ok) {
        const text = await res.text().catch(() => "");
        throw new Error(`HTTP ${res.status} ${res.statusText}${text ? ` - ${text}` : ""}`);
    }
    return res.json();
}

function renderEmptyState(message) {
    const statusDiv = document.getElementById("status");
    const resultsSection = document.getElementById("resultsSection");
    statusDiv.style.display = "block";
    statusDiv.innerText = message;
    resultsSection.innerHTML = "";
}

// ===================== Fonction principale =====================
async function fetchResults() {
    const statusDiv = document.getElementById("status");
    const resultsSection = document.getElementById("resultsSection");

    const dagRunId = getDagRunId();
    if (!dagRunId) {
        renderEmptyState("Aucun run trouvé. Lancez des validations puis revenez ici.");
        return;
    }

    const token = getAuthToken();
    if (!token) {
        window.location.href = "admin.html";
        return;
    }

    try {
        // Tentative immédiate (si le fichier de résultats existe déjà)
        const existing = await fetchJson(`${API_URL}/results/${dagRunId}`, token).catch(() => []);
        if (Array.isArray(existing) && existing.length > 0) {
            renderSummary(existing);
            renderResults(existing);
            statusDiv.style.display = "none";
            addPushAtlasButton();
            return;
        }

        statusDiv.style.display = "block";
        statusDiv.innerText = "Validation en cours…";

        let attempts = 0;
        let state = null;

        while (!["success", "failed"].includes(state) && attempts < MAX_ATTEMPTS) {
            const data = await fetchJson(`${API_URL}/dag-status/${dagRunId}`, token).catch(() => ({}));
            state = data?.state || null;

            if (!state || state === "running") {
                attempts += 1;
                statusDiv.innerText = `Validation en cours… (${attempts}/${MAX_ATTEMPTS})`;
                await new Promise((r) => setTimeout(r, POLL_INTERVAL_MS));
                continue;
            }
            break;
        }

        if (state !== "success") {
            if (state === "failed") renderEmptyState("La validation a échoué.");
            else renderEmptyState("Temps d'attente dépassé. Réessayez dans quelques instants.");
            return;
        }

        statusDiv.innerText = "Récupération des résultats…";
        const results = await fetchJson(`${API_URL}/results/${dagRunId}`, token);

        if (!Array.isArray(results) || results.length === 0) {
            renderEmptyState("Aucun résultat disponible.");
            return;
        }

        renderSummary(results);
        renderResults(results);
        statusDiv.style.display = "none";
        addPushAtlasButton();
    } catch (err) {
        console.error(err);
        statusDiv.style.display = "block";
        statusDiv.innerText = "Erreur lors de la récupération des résultats.";
        resultsSection.innerHTML = "";
    }
}
// ===================== RÉSUMÉ =====================
function renderSummary(data) {
    const container = document.querySelector('.container');

    const oldSummary = document.getElementById('summary');
    if (oldSummary) oldSummary.remove();

    let total = 0, success = 0, failed = 0;

    data.forEach(item => {
        if (item.status) {
            total++;
            const status = item.status.toLowerCase();

            if (status === "réussi") success++;
            else if (status === "échoué") failed++;
        }
    });

    const summaryDiv = document.createElement('div');
    summaryDiv.id = 'summary';
    summaryDiv.className = `dq-summary ${failed > 0 ? "dq-summary--failed" : "dq-summary--ok"}`;
    const rate = total ? ((success / total) * 100).toFixed(1) + "%" : "N/A";
    summaryDiv.innerHTML = `
        <div class="dq-summary__title">${failed > 0 ? "Attention" : "Tout est bon"}</div>
        <div class="dq-summary__stats">
            <span>Total: <strong>${total}</strong></span>
            <span>Réussis: <strong>${success}</strong></span>
            <span>Échoués: <strong>${failed}</strong></span>
            <span>Taux: <strong>${rate}</strong></span>
        </div>
    `;

    container.insertBefore(summaryDiv, container.firstChild.nextSibling);
}

// ===================== CARTES (UX: pas de dump technique par défaut) =====================
function renderResults(data) {
    const resultsSection = document.getElementById("resultsSection");
    resultsSection.innerHTML = "";

    const fragment = document.createDocumentFragment();

    (Array.isArray(data) ? data : []).forEach((item) => {
        const statusKey = normalizeStatus(item?.status);
        const ruleTitle = humanizeRuleType(item?.rule_type);
        const columnName = item?.column_name ? String(item.column_name) : null;
        const errorCount = item?.error_count !== undefined && item?.error_count !== null ? String(item.error_count) : null;
        const ratio = formatRatio(item?.ratio);

        const card = document.createElement("div");
        card.className = `dq-card dq-card--${statusKey}`;

        card.innerHTML = `
            <div class="dq-card__header">
                <div class="dq-card__title">
                    <div class="dq-card__rule">${escapeHtml(ruleTitle)}</div>
                    <div class="dq-card__subtitle">${columnName ? `Colonne: <strong>${escapeHtml(columnName)}</strong>` : "<span class=\"muted\">Dataset</span>"}</div>
                </div>
                <div class="dq-pill dq-pill--${statusKey}">
                    ${escapeHtml(item?.status || "Inconnu")}
                </div>
            </div>
            <div class="dq-card__meta">
                ${errorCount !== null ? `<div><span class="muted">Erreurs</span> <strong>${escapeHtml(errorCount)}</strong></div>` : ""}
                ${ratio ? `<div><span class="muted">Ratio</span> <strong>${escapeHtml(ratio)}</strong></div>` : ""}
            </div>
        `;

        const examples = Array.isArray(item?.examples) ? item.examples : [];
        if (statusKey === "failed" && examples.length > 0) {
            const exampleWrap = document.createElement("div");
            exampleWrap.className = "dq-examples";
            exampleWrap.innerHTML = `<div class="dq-examples__title">Exemples</div>`;

            const maxExamples = 3;
            examples.slice(0, maxExamples).forEach((ex) => {
                const box = document.createElement("div");
                box.className = "dq-example";

                if (ex && typeof ex === "object" && !Array.isArray(ex)) {
                    const entries = Object.entries(ex).slice(0, 8);
                    const rows = entries
                        .map(([k, v]) => `<div class="dq-example__row"><span class="dq-example__k">${escapeHtml(k)}</span><span class="dq-example__v">${escapeHtml(v)}</span></div>`)
                        .join("");
                    box.innerHTML = rows || `<div class="muted">Aucun détail exploitable.</div>`;
                } else {
                    box.textContent = String(ex);
                }
                exampleWrap.appendChild(box);
            });

            if (examples.length > maxExamples) {
                const more = document.createElement("div");
                more.className = "muted";
                more.textContent = `+${examples.length - maxExamples} autres exemple(s)`;
                exampleWrap.appendChild(more);
            }

            card.appendChild(exampleWrap);
        }

        // Détails techniques (optionnels)
        const details = document.createElement("details");
        details.className = "dq-details";
        details.innerHTML = `
            <summary>Voir les détails techniques</summary>
            <pre class="dq-details__pre">${escapeHtml(JSON.stringify(item, null, 2))}</pre>
        `;
        card.appendChild(details);

        fragment.appendChild(card);
    });

    resultsSection.appendChild(fragment);
}

// ===================== BOUTON =====================
function addPushAtlasButton() {
    if (document.getElementById('pushAtlasBtn')) return;

    const container = document.querySelector('.container');
    const pushButton = document.createElement('button');
    pushButton.id = 'pushAtlasBtn';
    pushButton.className = 'back-button';
    pushButton.textContent = 'Finaliser (push vers Atlas)';

    pushButton.onclick = () => finalizePushToAtlas(pushButton);

    container.appendChild(pushButton);
}

async function finalizePushToAtlas(pushButton) {
    const statusDiv = document.getElementById("status");
    const container = document.querySelector(".container");

    const token = getAuthToken();
    if (!token) {
        window.location.href = "index.html";
        return;
    }

    const datasetId = localStorage.getItem("last_uploaded_dataset_id");
    if (!datasetId) {
        renderEmptyState("Aucun dataset trouvé. Uploadez un dataset puis réessayez.");
        return;
    }

    pushButton.disabled = true;
    statusDiv.style.display = "block";
    statusDiv.innerText = "⏳ Synchronisation vers Atlas…";

    try {
        const res = await fetch(`${API_URL}/push-atlas/${datasetId}`, {
            method: "POST",
            headers: { Authorization: `Bearer ${token}` }
        });

        const text = await res.text().catch(() => "");
        if (!res.ok) {
            statusDiv.innerText = `❌ Push Atlas impossible.\n${text || ""}`;
            pushButton.disabled = false;
            return;
        }

        let data = {};
        try {
            data = JSON.parse(text);
        } catch {
            data = {};
        }

        if (data.dataset_guid) localStorage.setItem("last_atlas_guid", data.dataset_guid);
        if (data.column_guids && typeof data.column_guids === "object") {
            localStorage.setItem("last_column_guids", JSON.stringify(data.column_guids));
        }

        const applied = typeof data.column_classifications_applied === "number" ? data.column_classifications_applied : null;
        const errors = typeof data.column_classifications_errors === "number" ? data.column_classifications_errors : null;

        const extra = [
            applied !== null ? `🏷️ Classifications colonnes appliquées: ${applied}` : null,
            errors !== null && errors > 0 ? `⚠️ Erreurs classification colonnes: ${errors}` : null
        ].filter(Boolean).join("\n");

        statusDiv.innerText = `✅ Push Atlas terminé.${extra ? `\n${extra}` : ""}`;

        // Offer optional redirect to Grafana dashboards for the current project.
        const projectId = localStorage.getItem("current_project_id");
        const existingCta = document.getElementById("grafanaAfterAtlasCta");
        if (container && !existingCta) {
            const ctaWrap = document.createElement("div");
            ctaWrap.id = "grafanaAfterAtlasCta";
            ctaWrap.style.marginTop = "12px";
            ctaWrap.style.display = "flex";
            ctaWrap.style.gap = "10px";
            ctaWrap.style.flexWrap = "wrap";

            const homeBtn = document.createElement("button");
            homeBtn.className = "back-button";
            homeBtn.textContent = "Retour accueil";
            homeBtn.onclick = () => (window.location.href = "index.html");

            const grafanaBtn = document.createElement("button");
            grafanaBtn.className = "back-button";
            grafanaBtn.textContent = "Voir dashboards Grafana";
            grafanaBtn.disabled = !projectId;
            grafanaBtn.onclick = async () => {
                try {
                    if (!projectId) return;
                    grafanaBtn.disabled = true;
                    const resLinks = await fetch(`${API_URL}/projects/${projectId}/grafana-links`, {
                        headers: { Authorization: `Bearer ${token}` },
                        credentials: "include",
                    });
                    if (!resLinks.ok) throw new Error("Impossible de récupérer les liens Grafana");
                    const links = await resLinks.json();
                    const url = links && links.folder && links.folder.url ? `${API_URL}${links.folder.url}` : null;
                    if (!url) throw new Error("Lien Grafana manquant");
                    window.open(url, "_blank", "noopener");
                } catch (e) {
                    alert(`Erreur: ${e.message || e}`);
                } finally {
                    grafanaBtn.disabled = false;
                }
            };

            ctaWrap.appendChild(grafanaBtn);
            ctaWrap.appendChild(homeBtn);
            container.appendChild(ctaWrap);
        }
    } catch (err) {
        statusDiv.innerText = `❌ Erreur réseau: ${err.message || err}`;
        pushButton.disabled = false;
    }
}

document.addEventListener('DOMContentLoaded', fetchResults);
