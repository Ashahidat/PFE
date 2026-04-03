const API_URL = "http://localhost:8000";
window.columns = []; // initialisation

// ===================== GESTION DEEQU =====================
let deequRules = [];

function addDeequRule() {
    const ruleId = Date.now();
    deequRules.push({
        id: ruleId,
        type: "completeness",
        column: "",
        threshold: 1.0,
        values: []
    });
    renderDeequRules();
}

function removeDeequRule(ruleId) {
    deequRules = deequRules.filter(r => r.id !== ruleId);
    renderDeequRules();
}

function updateDeequRule(ruleId, field, value) {
    const rule = deequRules.find(r => r.id === ruleId);
    if (rule) {
        if (field === "values") {
            rule.values = value
                .split(",")
                .map(v => v.trim())
                .filter(v => v.length > 0);
        } else if (field === "threshold") {
            let parsed = Number(value);
            if (!Number.isFinite(parsed)) {
                parsed = rule.type === "completeness" ? 1.0 : 0;
            }
            if (rule.type === "completeness") {
                parsed = Math.max(0, Math.min(1, parsed));
            }
            rule.threshold = parsed;
        } else {
            rule[field] = value;
        }
    }
}

function renderDeequRules() {
    const container = document.getElementById("deequ-rules-list");
    if (!container) return;
    
    if (deequRules.length === 0) {
        container.innerHTML = '<p class="info-text">Aucune contrainte Deequ. Cliquez sur "Ajouter" pour commencer.</p>';
        return;
    }
    
    container.innerHTML = "";
    deequRules.forEach(rule => {
        const thresholdLabel =
            rule.type === "completeness"
                ? "Seuil de complétude:"
                : rule.type === "min"
                    ? "Valeur minimale attendue:"
                    : "Valeur maximale attendue:";
        const thresholdHint =
            rule.type === "completeness"
                ? "(0-1, ex: 0.95 = 95%)"
                : "(valeur numérique, ex: 18)";

        const ruleDiv = document.createElement("div");
        ruleDiv.className = "deequ-rule-card";
        ruleDiv.innerHTML = `
            <div class="rule-header">
                <strong>Contrainte #${rule.id}</strong>
                <button type="button" class="remove-rule-btn" data-id="${rule.id}">✖</button>
            </div>
            <div class="rule-fields">
                <label>Type:</label>
                <select class="deequ-type" data-id="${rule.id}">
                    <option value="completeness" ${rule.type === "completeness" ? "selected" : ""}>Complétude</option>
                    <option value="min" ${rule.type === "min" ? "selected" : ""}>Valeur minimale</option>
                    <option value="max" ${rule.type === "max" ? "selected" : ""}>Valeur maximale</option>
                    <option value="allowed_values" ${rule.type === "allowed_values" ? "selected" : ""}>Valeurs autorisées</option>
                </select>
                
                <label>Colonne:</label>
                <select class="deequ-column" data-id="${rule.id}">
                    <option value="">Sélectionner une colonne</option>
                    ${window.columns.map(col => `<option value="${col}" ${rule.column === col ? "selected" : ""}>${col}</option>`).join('')}
                </select>
                
                <div class="deequ-threshold-group" style="display: ${rule.type === 'allowed_values' ? 'none' : 'block'}">
                    <label>${thresholdLabel}</label>
                    <input type="number" class="deequ-threshold" data-id="${rule.id}" value="${rule.threshold}" step="0.01" ${rule.type === 'allowed_values' ? 'disabled' : ''}>
                    <small>${thresholdHint}</small>
                </div>
                
                <div class="deequ-values-group" style="display: ${rule.type === 'allowed_values' ? 'block' : 'none'}">
                    <label>Valeurs autorisées (séparées par des virgules):</label>
                    <input type="text" class="deequ-values" data-id="${rule.id}" value="${rule.values.join(', ')}" placeholder="ex: ACTIF, INACTIF, SUSPENDU">
                </div>
            </div>
        `;
        container.appendChild(ruleDiv);
    });
    
    // Attacher les événements
    document.querySelectorAll('.remove-rule-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const id = parseInt(btn.dataset.id);
            removeDeequRule(id);
        });
    });
    
    document.querySelectorAll('.deequ-type').forEach(select => {
        select.addEventListener('change', (e) => {
            const id = parseInt(select.dataset.id);
            const newType = select.value;
            updateDeequRule(id, "type", newType);

            // Re-render complet pour mettre à jour libellés/hints dynamiques
            renderDeequRules();
        });
    });
    
    document.querySelectorAll('.deequ-column').forEach(select => {
        select.addEventListener('change', (e) => {
            const id = parseInt(select.dataset.id);
            updateDeequRule(id, "column", select.value);
        });
    });
    
    document.querySelectorAll('.deequ-threshold').forEach(input => {
        input.addEventListener('input', (e) => {
            const id = parseInt(input.dataset.id);
            updateDeequRule(id, "threshold", input.value);
            input.value = deequRules.find(r => r.id === id)?.threshold ?? input.value;
        });
    });
    
    document.querySelectorAll('.deequ-values').forEach(input => {
        input.addEventListener('input', (e) => {
            const id = parseInt(input.dataset.id);
            updateDeequRule(id, "values", input.value);
        });
    });
}

// ===================== Chargement des colonnes =====================
async function loadColumns() {
    try {
        const token = localStorage.getItem("access_token");
        const dataset_id = localStorage.getItem("last_uploaded_dataset_id");
        if (!dataset_id) {
            console.error("❌ Aucun dataset_id trouvé dans localStorage");
            return;
        }

        const res = await fetch(`${API_URL}/get-columns/${dataset_id}`, {
            method: "GET",
            headers: { "Authorization": `Bearer ${token}` }
        });

        const data = await res.json();
        if (data.columns && Array.isArray(data.columns)) {
            window.columns = data.columns;
            console.log("📊 Colonnes chargées:", window.columns);
            renderDeequRules(); // Re-render si déjà ouvert
        } else {
            console.warn("⚠️ Aucune colonne reçue depuis l'API.");
        }
    } catch (err) {
        console.error("💥 Erreur chargement colonnes:", err);
    }
}

// ===================== Rendu des colonnes =====================
function renderDupColumns() {
    const container = document.getElementById("dupSensitive-select");
    if (!container) return;
    container.innerHTML = "";
    window.columns.forEach(col => {
        const div = document.createElement("div");
        div.innerHTML = `<label><input type="checkbox" class="dup-col" value="${col}"> ${col}</label>`;
        container.appendChild(div);
    });
}

function renderRegexColumns() {
    const types = [
        { id: "regex-email-select", className: "regex-email-col" },
        { id: "regex-phone-select", className: "regex-phone-col" },
        { id: "regex-postal-select", className: "regex-postal-col" }
    ];
    types.forEach(type => {
        const container = document.getElementById(type.id);
        if (!container) return;
        container.innerHTML = "";
        window.columns.forEach(col => {
            const div = document.createElement("div");
            div.innerHTML = `<label><input type="checkbox" class="${type.className}" value="${col}"> ${col}</label>`;
            container.appendChild(div);
        });
    });
}

// ===================== Listeners =====================
document.getElementById("dupSensitive")?.addEventListener("change", e => {
    const container = document.getElementById("dupSensitive-columns");
    container?.classList.toggle("hidden", !e.target.checked);
    if (e.target.checked) renderDupColumns();
});

document.getElementById("regexTest")?.addEventListener("change", e => {
    const container = document.getElementById("regex-columns");
    container?.classList.toggle("hidden", !e.target.checked);
    if (e.target.checked) renderRegexColumns();
});

// NOUVEAU : Listener Deequ
document.getElementById("deequTest")?.addEventListener("change", e => {
    const container = document.getElementById("deequ-container");
    container?.classList.toggle("hidden", !e.target.checked);
    if (e.target.checked && deequRules.length === 0) {
        addDeequRule(); // Ajouter une règle par défaut
    }
});

document.getElementById("addDeequRuleBtn")?.addEventListener("click", addDeequRule);

// ===================== Lancer le DAG =====================
document.getElementById("runDagBtn")?.addEventListener("click", async () => {
    const deequEnabled = document.getElementById("deequTest")?.checked;

    if (deequEnabled) {
        for (let i = 0; i < deequRules.length; i++) {
            const r = deequRules[i];
            const idx = i + 1;

            if (!r.column || !String(r.column).trim()) {
                alert(`La contrainte #${idx} (${r.type}) est incomplète : colonne obligatoire.`);
                return;
            }

            if (r.type === "allowed_values") {
                const vals = Array.isArray(r.values)
                    ? r.values.filter(v => String(v).trim().length > 0)
                    : [];
                if (vals.length === 0) {
                    alert(`La contrainte #${idx} (allowed_values) est incomplète : au moins une valeur autorisée est obligatoire.`);
                    return;
                }
            }

            if (r.type === "completeness") {
                const t = Number(r.threshold);
                if (!Number.isFinite(t) || t < 0 || t > 1) {
                    alert(`La contrainte #${idx} (completeness) est invalide : seuil attendu entre 0 et 1.`);
                    return;
                }
            }

            if (r.type === "min" || r.type === "max") {
                const t = Number(r.threshold);
                if (!Number.isFinite(t)) {
                    alert(`La contrainte #${idx} (${r.type}) est invalide : seuil numérique obligatoire.`);
                    return;
                }
            }
        }
    }

    // Construire les règles Deequ au bon format
    const deequRulesFormatted = deequRules
        .map(rule => {
            const baseRule = {
                type: rule.type,
                column: rule.column
            };
            if (rule.type === "allowed_values") {
                baseRule.values = rule.values;
            } else {
                baseRule.threshold = rule.threshold;
            }
            return baseRule;
        });
    
    console.log("[DEEQU][FRONT] deequRules brut:", deequRules);
    console.log("[DEEQU][FRONT] deequRules formaté:", deequRulesFormatted);
    
    const rules = {
        duplicates: {
            sensitive: document.getElementById("dupSensitive")?.checked ?
                Array.from(document.querySelectorAll(".dup-col:checked")).map(e => e.value) : [],
            full_row: document.getElementById("dupFull")?.checked || false
        },
        regex: {
            email: document.getElementById("regexTest")?.checked ?
                Array.from(document.querySelectorAll(".regex-email-col:checked")).map(e => e.value) : [],
            phone: document.getElementById("regexTest")?.checked ?
                Array.from(document.querySelectorAll(".regex-phone-col:checked")).map(e => e.value) : [],
            postal_code: document.getElementById("regexTest")?.checked ?
                Array.from(document.querySelectorAll(".regex-postal-col:checked")).map(e => e.value) : []
        },
        deequ: document.getElementById("deequTest")?.checked ? deequRulesFormatted : []  // ← NOUVEAU
    };
    console.log("[DEEQU][FRONT] payload /run-dag-v2:", { rules, dataset_id: localStorage.getItem("last_uploaded_dataset_id") });

    const token = localStorage.getItem("access_token");
    const dataset_id = localStorage.getItem("last_uploaded_dataset_id");
    if (!dataset_id) return alert("Impossible de lancer le DAG sans dataset.");

    try {
        const res = await fetch(`${API_URL}/run-dag-v2`, {
            method: "POST",
            headers: { "Content-Type": "application/json", "Authorization": `Bearer ${token}` },
            body: JSON.stringify({ rules, dataset_id })
        });

        const data = await res.json();
        console.log("[DEEQU][FRONT] réponse /run-dag-v2:", data);
        if (data.dag_run_id) {
            localStorage.setItem("last_dag_run_id", data.dag_run_id);
            alert("✅ DAG lancé !");
            window.location.href = "results.html";
        } else {
            console.error(data);
            alert("❌ Erreur lancement DAG");
        }
    } catch (err) {
        console.error(err);
        alert("❌ Erreur lancement DAG");
    }
});

// ===================== Vérifier le statut du DAG =====================
async function checkDagStatus() {
    const dag_run_id = localStorage.getItem("last_dag_run_id");
    if (!dag_run_id) return;

    const token = localStorage.getItem("access_token");
    try {
        const res = await fetch(`${API_URL}/dag-status/${dag_run_id}`, {
            headers: { "Authorization": `Bearer ${token}` }
        });
        const data = await res.json();
        console.log("Etat du DAG :", data.state);
        return data.state;
    } catch (err) {
        console.error("Erreur récupération statut DAG :", err);
    }
}

// ===================== Initialisation =====================
loadColumns();
