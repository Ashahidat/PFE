// js/describe.js
const API_URL = "http://localhost:8000";

// Éléments DOM
const datasetNameEl = document.getElementById('datasetName');
const datasetMetaEl = document.getElementById('datasetMeta');
const columnsListEl = document.getElementById('columnsList');
const describeForm = document.getElementById('describeForm');
const saveBtn = document.getElementById('saveBtn');
const skipBtn = document.getElementById('skipBtn');
const statusMessage = document.getElementById('statusMessage');

let currentDatasetId = null;

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
    
    // 🔥 NOUVEAU : Charger les suggestions d'héritage
    await loadInheritedDescriptions();
    await loadParentSuggestions();
    
    // Écouteurs d'événements
    describeForm.addEventListener('submit', saveDescriptions);
    skipBtn.addEventListener('click', skipToTests);
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
            const input = document.querySelector(`[data-column="${escapeHtml(desc.column_name)}"]`);
            if (input) {
                input.value = desc.description;
                input.classList.add('completed');
            }
        });
        
    } catch (error) {
        console.error('Erreur chargement descriptions:', error);
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
            <input type="text" 
                   class="column-description-input" 
                   data-column="${escapeHtml(column)}"
                   placeholder="Décrivez cette colonne..."
                   autocomplete="off">
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
    });
    
    console.log(`✅ ${filledCount}/${inputs.length} inputs remplis`);
    console.log(`📦 Données à envoyer:`, descriptionsData);
    console.groupEnd();
    
    return descriptionsData;
}

// ===================== SAUVEGARDE =====================
async function saveDescriptions(e) {
    e.preventDefault();
    
    // 🔥 DEBUG: Afficher l'état avant sauvegarde
    const descriptions = debugDescriptionsBeforeSave();
    
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
        console.log("📤 Envoi au backend:", JSON.stringify({ descriptions }, null, 2));
        
        const response = await fetch(`${API_URL}/api/datasets/${currentDatasetId}/descriptions`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({ descriptions })
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