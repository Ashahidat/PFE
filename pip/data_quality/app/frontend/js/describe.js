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
                    appliedCount++;
                }
            });
            
            if (appliedCount > 0) {
                showStatus(`✅ ${appliedCount} descriptions héritées`, 'success');
            }
            
            btn.textContent = '✓ Hérité';
            btn.disabled = true;
        });
    });
}

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
    
    // Appliquer une suggestion individuelle
    panel.querySelectorAll('.apply-suggestion').forEach(btn => {
        btn.addEventListener('click', () => {
            const colName = btn.dataset.column;
            const desc = btn.dataset.desc;
            const input = document.querySelector(`[data-column="${colName}"]`);
            
            if (input && !input.value.trim()) {
                input.value = desc;
                input.classList.add('completed');
                btn.textContent = '✓';
                btn.disabled = true;
            }
        });
    });
    
    // Tout appliquer
    panel.querySelector('#applyAllSuggestions').addEventListener('click', () => {
        suggestions.forEach(sugg => {
            const input = document.querySelector(`[data-column="${escapeHtml(sugg.column_name)}"]`);
            if (input && !input.value.trim()) {
                input.value = sugg.description;
                input.classList.add('completed');
            }
        });
        
        panel.querySelectorAll('.apply-suggestion').forEach(btn => {
            btn.textContent = '✓';
            btn.disabled = true;
        });
        
        showStatus(`✅ Suggestions appliquées`, 'success');
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

// ===================== SAUVEGARDE =====================
async function saveDescriptions(e) {
    e.preventDefault();
    
    // Récupérer toutes les descriptions
    const descriptions = [];
    document.querySelectorAll('.column-description-input').forEach(input => {
        const desc = input.value.trim();
        if (desc) {
            descriptions.push({
                column_name: input.dataset.column,
                description: desc
            });
        }
    });
    
    if (descriptions.length === 0) {
        if (!confirm('Aucune description saisie. Voulez-vous vraiment continuer ?')) {
            return;
        }
    }
    
    // Désactiver les boutons
    setButtonsDisabled(true);
    showStatus('Enregistrement en cours...', 'info');
    
    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch(`${API_URL}/api/datasets/${currentDatasetId}/descriptions`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({ descriptions })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Erreur sauvegarde');
        }
        
        const result = await response.json();
        
        showStatus(`✅ ${result.saved_count} descriptions enregistrées ! Redirection...`, 'success');
        
        // Redirection automatique vers tests
        setTimeout(() => {
            window.location.href = 'tests.html';
        }, 1500);
        
    } catch (error) {
        console.error('Erreur:', error);
        showStatus('❌ Erreur lors de la sauvegarde', 'error');
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