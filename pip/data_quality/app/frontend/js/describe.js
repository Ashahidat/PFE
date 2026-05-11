// js/describe.js
const API_URL = window.API_URL || window.location.origin;

// Éléments DOM
const datasetNameEl = document.getElementById('datasetName');
const datasetMetaEl = document.getElementById('datasetMeta');
const columnsListEl = document.getElementById('columnsList');
const describeForm = document.getElementById('describeForm');
const saveBtn = document.getElementById('saveBtn');
const skipBtn = document.getElementById('skipBtn');
const statusMessage = document.getElementById('statusMessage');
const assignmentTermSelect = document.getElementById('assignmentTermSelect');
const assignmentColumnSelect = document.getElementById('assignmentColumnSelect');
const assignmentStatus = document.getElementById('assignmentStatus');
const assignedListEl = document.getElementById('assignedList');

let assignmentTerms = [];
let assignmentCategories = [];

let currentDatasetId = null;

function cssEscape(value) {
    if (window.CSS && typeof window.CSS.escape === "function") {
        return window.CSS.escape(String(value));
    }
    return String(value).replace(/"/g, '\\"');
}

async function loadAssignmentCategories() {
    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch(`${API_URL}/glossary/categories`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if (!response.ok) return;
        assignmentCategories = await response.json();
        refreshAssignmentCategorySelect();
    } catch (error) {
        console.error("Erreur chargement catégories", error);
    }
}

function refreshAssignmentCategorySelect() {
    const select = document.getElementById('assignmentCategorySelect');
    if (!select) return;
    select.innerHTML = "<option value=''>Toutes catégories</option>" +
        assignmentCategories.map((category) => `<option value="${category.id}">${escapeHtml(category.name)}</option>`).join("");
}

function refreshAssignmentTermSelect(categoryId = "") {
    if (!assignmentTermSelect) return;
    const filtered = categoryId
        ? assignmentTerms.filter((t) => String(t.category_id) === String(categoryId))
        : assignmentTerms;
    if (!filtered.length) {
        assignmentTermSelect.innerHTML = "<option value=''>Aucun terme disponible</option>";
        return;
    }
    const hideCategory = Boolean(categoryId);
    assignmentTermSelect.innerHTML = filtered
        .map((t) => {
            const label = hideCategory
                ? escapeHtml(t.term)
                : `${escapeHtml(t.term)} (${escapeHtml(t.category_name || '—')})`;
            return `<option value="${t.id}">${label}</option>`;
        })
        .join("");
}

// ===================== INITIALISATION =====================
document.addEventListener('DOMContentLoaded', async () => {
    // Récupérer l'ID depuis l'URL ou localStorage
    const urlParams = new URLSearchParams(window.location.search);
    currentDatasetId = urlParams.get('dataset_id') || localStorage.getItem('last_uploaded_dataset_id');
    
    if (!currentDatasetId) {
        showStatus('Aucun dataset trouvé. Redirection...', 'error');
        setTimeout(() => window.location.href = 'index.html', 2000);
        return;
    }
    
    // Sauvegarder dans localStorage pour les autres pages
    localStorage.setItem('last_uploaded_dataset_id', currentDatasetId);
    
    // Charger les données
    await loadDatasetInfo();
    await loadExistingDescriptions();
    await loadExistingClassifications();
    
    // 🔥 NOUVEAU : Charger les suggestions d'héritage
    await loadInheritedDescriptions();
    await loadParentSuggestions();
    
    // Écouteurs d'événements
    describeForm.addEventListener('submit', saveDescriptions);
    skipBtn.addEventListener('click', skipToTests);
    document.getElementById('assignTermBtn').addEventListener('click', assignTermToDataset);
    const assignmentCategorySelectEl = document.getElementById('assignmentCategorySelect');
    if (assignmentCategorySelectEl) {
        assignmentCategorySelectEl.addEventListener('change', (event) => {
            refreshAssignmentTermSelect(event.target.value);
        });
    }
    await loadAssignmentCategories();
    await loadGlossaryTermsForAssignment();
    await refreshAssignments();
});

// ===================== CHARGEMENT DES DONNÉES =====================
async function loadDatasetInfo() {
    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch(`${API_URL}/api/datasets/${currentDatasetId}/simple-info`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (!response.ok) throw new Error('Erreur chargement dataset');
        
        const dataset = await response.json();
        
        // Afficher les infos
        datasetNameEl.textContent = dataset.name;
        datasetMetaEl.textContent = `${dataset.columns_list.length} colonnes à décrire`;
        
        // Générer le formulaire
        renderColumnsForm(dataset.columns_list);
        populateAssignmentColumns(dataset.columns_list);
        
    } catch (error) {
        console.error('Erreur:', error);
        showStatus('Erreur de chargement du dataset', 'error');
    }
}

async function loadExistingDescriptions() {
    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch(`${API_URL}/api/datasets/${currentDatasetId}/descriptions`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (!response.ok) return;
        
        const descriptions = await response.json();
        
        // Pré-remplir les inputs
        descriptions.forEach(desc => {
            const input = document.querySelector(`.column-description-input[data-column="${cssEscape(desc.column_name)}"]`);
            if (input) {
                input.value = desc.description;
                input.classList.add('completed');
            }
        });
        
    } catch (error) {
        console.error('Erreur chargement descriptions:', error);
    }
}

async function loadExistingClassifications() {
    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch(`${API_URL}/api/datasets/${currentDatasetId}/column-classifications`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });

        if (!response.ok) return;

        const rows = await response.json();
        rows.forEach(row => {
            const select = document.querySelector(`.column-classification-select[data-column="${cssEscape(row.column_name)}"]`);
            if (select) {
                select.value = row.classification_name || "NONE";
            }
        });
    } catch (error) {
        console.error('Erreur chargement classifications:', error);
    }
}

// ===================== 🔥 NOUVELLES FONCTIONS D'HÉRITAGE =====================

async function loadInheritedDescriptions() {
    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch(`${API_URL}/api/datasets/${currentDatasetId}/inherited-descriptions`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (!response.ok) return;
        
        const data = await response.json();
        
        if (data.versions && data.versions.length > 0) {
            showInheritancePanel(data.versions);
        }
    } catch (error) {
        console.error('Erreur chargement héritage:', error);
    }
}

async function loadParentSuggestions() {
    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch(`${API_URL}/api/datasets/${currentDatasetId}/parent-suggestions`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (!response.ok) return;
        
        const data = await response.json();
        
        if (data.has_parent && data.suggestions && data.suggestions.length > 0) {
            showParentSuggestionsPanel(data.suggestions);
        }
    } catch (error) {
        console.error('Erreur chargement suggestions parent:', error);
    }
}

async function loadGlossaryTermsForAssignment() {
    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch(`${API_URL}/glossary/terms`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if (!response.ok) return;
        assignmentTerms = await response.json();
        const selectedCat = document.getElementById('assignmentCategorySelect')?.value || "";
        refreshAssignmentTermSelect(selectedCat);
    } catch (error) {
        console.error("Erreur chargement termes pour assignation :", error);
    }
}

function populateAssignmentColumns(columns) {
    assignmentColumnSelect.innerHTML = "<option value=''>Tout le dataset</option>" +
        columns.map((col) => `<option value="${col}">${escapeHtml(col)}</option>`).join('');
}

async function assignTermToDataset() {
    const termId = assignmentTermSelect.value;
    const columnName = assignmentColumnSelect.value || null;
    if (!currentDatasetId || !termId) {
        assignmentStatus.textContent = "Sélectionne un terme";
        assignmentStatus.style.color = "red";
        return;
    }

    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch(`${API_URL}/glossary/datasets/${currentDatasetId}/terms`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({ term_id: termId, column_name: columnName })
        });
        if (!response.ok) {
            const err = await response.json();
            assignmentStatus.textContent = err.detail || "Erreur d'assignation";
            assignmentStatus.style.color = "red";
            return;
        }
        assignmentStatus.textContent = "✅ Terme assigné";
        assignmentStatus.style.color = "green";
        refreshAssignments();
    } catch (error) {
        assignmentStatus.textContent = "Erreur de connexion";
        assignmentStatus.style.color = "red";
    }
}

async function refreshAssignments() {
    if (!currentDatasetId) return;
    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch(`${API_URL}/glossary/datasets/${currentDatasetId}/terms`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if (!response.ok) throw new Error('Impossible de charger les assignations');
        const assignments = await response.json();
        renderAssignmentList(assignments);
    } catch (error) {
        console.error("Erreur refreshAssignments:", error);
        assignedListEl.innerHTML = '<p style="color:red;">Impossible de charger les assignations</p>';
    }
}

function renderAssignmentList(assignments) {
    if (!assignments.length) {
        assignedListEl.innerHTML = "<p>Aucun terme assigné</p>";
        return;
    }
    assignedListEl.innerHTML = assignments
        .map((assignment) => `
            <div class="term-item">
                <div>
                    <strong>${escapeHtml(assignment.term)}</strong>
                    <p style="margin:4px 0;">Glossaire : ${escapeHtml(assignment.glossary_name || '')} · Catégorie : ${escapeHtml(assignment.category || '—')}</p>
                    <p style="margin:4px 0; font-size:12px;">Colonne : ${escapeHtml(assignment.column_name || 'entier')}</p>
                </div>
                <button class="btn-delete" onclick="removeAssignment(${assignment.glossary_term_id}, '${assignment.column_name || ''}')">Retirer</button>
            </div>`
        )
        .join('');
}

async function removeAssignment(termId, columnName) {
    try {
        const token = localStorage.getItem('access_token');
        const url = new URL(`${API_URL}/glossary/datasets/${currentDatasetId}/terms/${termId}`);
        if (columnName) url.searchParams.append('column_name', columnName);
        await fetch(url.toString(), {
            method: 'DELETE',
            headers: { 'Authorization': `Bearer ${token}` }
        });
        refreshAssignments();
    } catch (error) {
        console.error("Erreur suppression assignation :", error);
    }
}

// 🔥 NOUVELLE FONCTION : Remplissage automatique des suggestions
function autoFillEmptyFieldsWithSuggestions() {
    const suggestionsPanel = document.querySelector('.suggestions-panel');
    if (!suggestionsPanel) {
        console.log("ℹ️ Aucun panneau de suggestions trouvé");
        return 0;
    }
    
    const suggestionItems = suggestionsPanel.querySelectorAll('.suggestion-item');
    let filledCount = 0;
    
    suggestionItems.forEach(item => {
        const columnSpan = item.querySelector('.suggestion-column');
        const descSpan = item.querySelector('.suggestion-desc');
        const applyBtn = item.querySelector('.apply-suggestion');
        
        if (columnSpan && descSpan) {
            // Nettoyer le texte de la colonne (enlever l'emoji 📌 si présent)
            let columnName = columnSpan.textContent;
            columnName = columnName.replace(/[📌]/g, '').trim();
            
            const description = descSpan.textContent;
            // Nettoyer la description (enlever 💡 ou ⚠️)
            const cleanDescription = description.replace(/[💡⚠️]/g, '').trim();
            
            const input = document.querySelector(`.column-description-input[data-column="${columnName}"]`);
            
            if (input && !input.value.trim()) {
                input.value = cleanDescription;
                input.classList.add('completed');
                input.dispatchEvent(new Event('input', { bubbles: true }));
                
                // Désactiver le bouton d'application
                if (applyBtn) {
                    applyBtn.textContent = '✓ Auto-rempli';
                    applyBtn.disabled = true;
                }
                
                filledCount++;
                console.log(`✅ Auto-rempli: ${columnName} = "${cleanDescription}"`);
            }
        }
    });
    
    if (filledCount > 0) {
        showStatus(`🤖 ${filledCount} suggestions appliquées automatiquement`, 'success');
    }
    
    return filledCount;
}

// Dans la fonction showInheritancePanel
function showInheritancePanel(versions) {
    const panel = document.createElement('div');
    panel.className = 'inheritance-panel';
    panel.innerHTML = `
        <h4>📋 Versions précédentes</h4>
        <p>Des descriptions existent dans les versions précédentes :</p>
    `;
    
    versions.forEach(version => {
        const versionDiv = document.createElement('div');
        versionDiv.className = 'version-card';
        versionDiv.innerHTML = `
            <div class="version-header">
                <strong>Version ${version.version_number}</strong>
                <small>${version.created_at ? new Date(version.created_at).toLocaleDateString() : ''}</small>
            </div>
            <div class="version-preview">
                ${version.descriptions.slice(0, 3).map(d => 
                    `<div><strong>${escapeHtml(d.column_name)}</strong> : ${escapeHtml(d.description.substring(0, 30))}...</div>`
                ).join('')}
                ${version.descriptions.length > 3 ? `<div>... et ${version.descriptions.length - 3} autres</div>` : ''}
            </div>
            <button class="btn-small inherit-version" data-version='${JSON.stringify(version.descriptions)}'>
                Utiliser cette version
            </button>
        `;
        panel.appendChild(versionDiv);
    });
    
    document.querySelector('.form-header').after(panel);
    
    // Gérer les clics sur les boutons d'héritage
    panel.querySelectorAll('.inherit-version').forEach(btn => {
        btn.addEventListener('click', () => {
            const descriptions = JSON.parse(btn.dataset.version);
            let appliedCount = 0;
            
            descriptions.forEach(desc => {
                const input = document.querySelector(`[data-column="${escapeHtml(desc.column_name)}"]`);
                if (input && !input.value.trim()) {
                    input.value = desc.description;
                    input.classList.add('completed');
                    // 🔥 DÉCLENCHER L'ÉVÉNEMENT input POUR METTRE À JOUR L'ÉTAT
                    input.dispatchEvent(new Event('input', { bubbles: true }));
                    appliedCount++;
                }
            });
            
            if (appliedCount > 0) {
                showStatus(`✅ ${appliedCount} descriptions héritées`, 'success');
            } else {
                showStatus(`ℹ️ ${appliedCount} nouvelles descriptions ajoutées (les autres étaient déjà remplies)`, 'info');
            }
            
            btn.textContent = '✓ Hérité';
            btn.disabled = true;
        });
    });
}

// 🔥 VERSION MODIFIÉE de showParentSuggestionsPanel avec auto-remplissage
function showParentSuggestionsPanel(suggestions) {
    const panel = document.createElement('div');
    panel.className = 'suggestions-panel';
    panel.innerHTML = `
        <h4>💡 Suggestions depuis d'autres datasets</h4>
        <p>Des datasets similaires ont ces descriptions :</p>
        <div class="suggestions-list"></div>
        <button class="btn-info" id="applyAllSuggestions">Tout appliquer</button>
    `;
    
    const listDiv = panel.querySelector('.suggestions-list');
    
    suggestions.forEach(sugg => {
        const suggDiv = document.createElement('div');
        suggDiv.className = 'suggestion-item';
        suggDiv.innerHTML = `
            <span class="suggestion-column">${escapeHtml(sugg.column_name)}</span>
            <span class="suggestion-desc">${escapeHtml(sugg.description)}</span>
            <button class="btn-small apply-suggestion" data-column="${escapeHtml(sugg.column_name)}" data-desc="${escapeHtml(sugg.description)}">
                Appliquer
            </button>
        `;
        listDiv.appendChild(suggDiv);
    });
    
    document.querySelector('.form-header').after(panel);
    
    // 🔥 NOUVEAU : Remplir automatiquement les champs vides
    setTimeout(() => {
        const filledCount = autoFillEmptyFieldsWithSuggestions();
        if (filledCount > 0) {
            console.log(`🎉 ${filledCount} champs remplis automatiquement !`);
        }
    }, 100);
    
    // Appliquer une suggestion individuelle
    panel.querySelectorAll('.apply-suggestion').forEach(btn => {
        btn.addEventListener('click', () => {
            const colName = btn.dataset.column;
            const desc = btn.dataset.desc;
            const input = document.querySelector(`[data-column="${colName}"]`);
            
            if (input && !input.value.trim()) {
                input.value = desc;
                input.classList.add('completed');
                // 🔥 DÉCLENCHER L'ÉVÉNEMENT input
                input.dispatchEvent(new Event('input', { bubbles: true }));
                btn.textContent = '✓';
                btn.disabled = true;
                showStatus(`✅ Description appliquée pour "${colName}"`, 'success');
            } else if (input && input.value.trim()) {
                showStatus(`⚠️ "${colName}" a déjà une description`, 'info');
            }
        });
    });
    
    // Tout appliquer
    panel.querySelector('#applyAllSuggestions').addEventListener('click', () => {
        let appliedCount = 0;
        let alreadyFilledCount = 0;
        
        suggestions.forEach(sugg => {
            const input = document.querySelector(`[data-column="${escapeHtml(sugg.column_name)}"]`);
            if (input && !input.value.trim()) {
                input.value = sugg.description;
                input.classList.add('completed');
                // 🔥 DÉCLENCHER L'ÉVÉNEMENT input
                input.dispatchEvent(new Event('input', { bubbles: true }));
                appliedCount++;
            } else if (input && input.value.trim()) {
                alreadyFilledCount++;
            }
        });
        
        panel.querySelectorAll('.apply-suggestion').forEach(btn => {
            btn.textContent = '✓';
            btn.disabled = true;
        });
        
        if (appliedCount > 0) {
            showStatus(`✅ ${appliedCount} suggestions appliquées${alreadyFilledCount > 0 ? ` (${alreadyFilledCount} déjà remplies)` : ''}`, 'success');
        } else {
            showStatus(`ℹ️ Aucune nouvelle suggestion à appliquer (${alreadyFilledCount} déjà remplies)`, 'info');
        }
    });
}

// ===================== RENDU DU FORMULAIRE =====================
function renderColumnsForm(columns) {
    columnsListEl.innerHTML = '';
    
    columns.forEach(column => {
        const columnItem = document.createElement('div');
        columnItem.className = 'column-item';
        
        columnItem.innerHTML = `
            <div class="column-header">
                <span class="column-name">${escapeHtml(column)}</span>
            </div>
            <div class="column-controls">
                <input type="text" 
                       class="column-description-input" 
                       data-column="${escapeHtml(column)}"
                       placeholder="Décrivez cette colonne..."
                       autocomplete="off">
                <select class="column-classification-select" data-column="${escapeHtml(column)}" aria-label="Classification">
                    <option value="NONE">Aucune</option>
                    <option value="PII">PII</option>
                    <option value="SENSITIVE">SENSITIVE</option>
                </select>
            </div>
        `;
        
        columnsListEl.appendChild(columnItem);
    });
    
    // Ajouter l'écouteur pour le style "completed"
    document.querySelectorAll('.column-description-input').forEach(input => {
        input.addEventListener('input', function() {
            if (this.value.trim()) {
                this.classList.add('completed');
            } else {
                this.classList.remove('completed');
            }
        });
    });
}

// ===================== FONCTIONS DEBUG =====================
function debugDescriptionsBeforeSave() {
    console.group("🔍 DEBUG SAVE DESCRIPTIONS");
    
    const inputs = document.querySelectorAll('.column-description-input');
    console.log(`📊 Nombre total d'inputs: ${inputs.length}`);
    
    let filledCount = 0;
    const descriptionsData = [];
    const classificationsData = [];
    
    inputs.forEach((input, idx) => {
        const rawValue = input.value;
        const trimmedValue = rawValue.trim();
        const columnName = input.getAttribute('data-column');
        const datasetColumn = input.dataset.column;
        
        const isFilled = trimmedValue.length > 0;
        if (isFilled) filledCount++;
        
        console.log(`[${idx}]`, {
            'data-column (attr)': columnName,
            'dataset.column': datasetColumn,
            'raw value': rawValue,
            'trimmed length': trimmedValue.length,
            'filled': isFilled,
            'html': input.outerHTML.substring(0, 100)
        });
        
        if (isFilled) {
            descriptionsData.push({
                column_name: columnName || datasetColumn,
                description: trimmedValue
            });
        }

        const select = document.querySelector(`.column-classification-select[data-column="${cssEscape(columnName || datasetColumn)}"]`);
        if (select) {
            const value = (select.value || "NONE").toUpperCase();
            classificationsData.push({
                column_name: columnName || datasetColumn,
                classification_name: value === "NONE" ? null : value
            });
        }
    });
    
    console.log(`✅ ${filledCount}/${inputs.length} inputs remplis`);
    console.log(`📦 Données à envoyer:`, descriptionsData);
    console.log(`🏷️ Classifications à envoyer:`, classificationsData.filter(x => x.classification_name));
    console.groupEnd();
    
    return { descriptionsData, classificationsData };
}

// ===================== SAUVEGARDE =====================
async function saveDescriptions(e) {
    e.preventDefault();
    
    // 🔥 DEBUG: Afficher l'état avant sauvegarde
    const { descriptionsData: descriptions, classificationsData } = debugDescriptionsBeforeSave();
    
    if (descriptions.length === 0) {
        console.warn("⚠️ Aucune description trouvée!");
        if (!confirm('Aucune description saisie. Voulez-vous vraiment continuer sans descriptions ?')) {
            return;
        }
    }
    
    // Désactiver les boutons
    setButtonsDisabled(true);
    showStatus(`💾 Sauvegarde de ${descriptions.length} description(s) en cours...`, 'info');
    
    try {
        const token = localStorage.getItem('access_token');
        console.log("📤 Envoi au backend:", JSON.stringify({ descriptions, classifications: classificationsData }, null, 2));
        
        const response = await fetch(`${API_URL}/api/datasets/${currentDatasetId}/descriptions`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({ descriptions, classifications: classificationsData })
        });
        
        console.log("📥 Réponse backend:", {
            status: response.status,
            statusText: response.statusText
        });
        
        if (!response.ok) {
            const error = await response.json();
            console.error("❌ Erreur backend:", error);
            throw new Error(error.detail || 'Erreur sauvegarde');
        }
        
        const result = await response.json();
        console.log("✅ Résultat:", result);
        
        showStatus(`✅ ${result.saved_count} descriptions enregistrées ! Redirection...`, 'success');
        
        setTimeout(() => {
            window.location.href = 'tests.html';
        }, 1500);
        
    } catch (error) {
        console.error('❌ Erreur:', error);
        showStatus('❌ Erreur lors de la sauvegarde: ' + error.message, 'error');
        setButtonsDisabled(false);
    }
}

// ===================== ACTIONS =====================
function skipToTests() {
    if (confirm('Passer directement aux tests de qualité ?')) {
        window.location.href = 'tests.html';
    }
}

function setButtonsDisabled(disabled) {
    saveBtn.disabled = disabled;
    skipBtn.disabled = disabled;
}

function showStatus(message, type) {
    statusMessage.textContent = message;
    statusMessage.className = `status-message ${type}`;
    statusMessage.classList.remove('hidden');
    
    // Cacher après 5 secondes pour les messages de succès/info
    if (type !== 'error') {
        setTimeout(() => {
            statusMessage.classList.add('hidden');
        }, 5000);
    }
}

// ===================== UTILITAIRES =====================
function escapeHtml(unsafe) {
    if (!unsafe) return '';
    return String(unsafe)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}
