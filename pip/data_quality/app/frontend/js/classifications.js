/* ============================
   classifications.js - SIMPLIFIÉ
   ============================ */

const API_URL = window.API_URL || "http://localhost:8000";

console.log("✅ classifications.js chargé - API_URL:", API_URL);

/* ----------------------------
   Définition des attributs - AUCUN ATTRIBUT
----------------------------- */
const CLASSIFICATION_ATTRIBUTES = {
  PUBLIC: [],      // No attributes
  RESTRICTED: []   // NO mandatory department attribute - just the name indicates restriction
};

// Classifications pour colonnes - SIMPLIFIÉES
const COLUMN_CLASSIFICATIONS = {
  PII: { label: "PII (email, téléphone, nom, etc.)", attributes: [] },
  SENSITIVE: { label: "Sensible (médicale, financière)", attributes: [] }
};

/* ----------------------------
   Fonction pour appliquer classification de colonne
----------------------------- */
async function applyColumnClassification(columnName, classification, datasetId, atlasGuid) {
  const token = localStorage.getItem("access_token");
  
  const payload = {
    entity_type: "COLUMN",
    entity_id: datasetId,
    atlas_guid: atlasGuid,
    classification_name: classification,
    column_name: columnName,
    attributes: {}  // No attributes for PII/SENSITIVE
  };
  
  console.log("📤 Application classification colonne:", payload);
  
  try {
    const res = await fetch(`${API_URL}/apply-classification`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`
      },
      body: JSON.stringify(payload)
    });
    
    if (!res.ok) {
      const errorText = await res.text();
      throw new Error(`Erreur ${res.status}: ${errorText}`);
    }
    
    const result = await res.json();
    console.log(`✅ Classification "${classification}" appliquée à "${columnName}"`);
    return result;
    
  } catch (error) {
    console.error("Erreur application classification colonne:", error);
    throw error;
  }
}

/* ----------------------------
   Récupérer les classifications autorisées
----------------------------- */
async function getAllowedClassifications(datasetId) {
  const token = localStorage.getItem("access_token");
  
  try {
    const res = await fetch(`${API_URL}/dataset/${datasetId}/allowed-classifications`, {
      headers: {
        Authorization: `Bearer ${token}`
      }
    });
    
    if (res.ok) {
      return await res.json();
    }
    return { allowed: [], dataset_classification: null };
  } catch (error) {
    console.error("Erreur récupération classifications:", error);
    return { allowed: [], dataset_classification: null };
  }
}

/* ----------------------------
   UI dynamique
----------------------------- */
document.addEventListener("DOMContentLoaded", () => {
  console.log("✅ DOM Content Loaded - classifications.js");
  initDatasetUI();
});

function initDatasetUI() {
  const select = document.getElementById("classificationSelect");
  const container = document.getElementById("attributesContainer");
  const applyBtn = document.getElementById("applyClassificationBtn");

  if (!select || !applyBtn) {
    console.error("❌ Éléments UI dataset introuvables");
    return;
  }

  // Définir RESTRICTED comme valeur par défaut
  select.value = "RESTRICTED";
  
  // NO ATTRIBUTES - container remains empty
  container.innerHTML = "";  // Empty - no mandatory department field

  select.onchange = () => {
    container.innerHTML = "";  // Always empty - no attributes for either classification
  };

  applyBtn.onclick = async () => {
    console.log("🔄 Application classification dataset...");
    
    const token = localStorage.getItem("access_token");
    const datasetId = localStorage.getItem("last_uploaded_dataset_id");
    const atlasGuid = localStorage.getItem("last_atlas_guid");

    if (!token) {
      alert("❌ Token manquant. Veuillez vous reconnecter.");
      return;
    }
    
    if (!datasetId) {
      alert("❌ Dataset ID manquant. Veuillez d'abord uploader un dataset.");
      return;
    }
    
    if (!atlasGuid) {
      alert("❌ Atlas GUID manquant. Veuillez d'abord pousser vers Atlas.");
      return;
    }

    const classification = select.value;
    if (!classification) {
      alert("❌ Choisis une classification.");
      return;
    }

    // NO ATTRIBUTES - always empty object
    const attributes = {};
    
    const payload = {
      entity_type: "DATASET",
      entity_id: datasetId,
      atlas_guid: atlasGuid,
      classification_name: classification,
      attributes: attributes  // Always empty
    };
    
    console.log("📤 Payload dataset à envoyer:", payload);

    try {
      const res = await fetch(`${API_URL}/apply-classification`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify(payload)
      });

      const text = await res.text();

      if (!res.ok) {
        console.error("❌ Erreur serveur:", text);
        alert("❌ Erreur classification\n" + text);
        return;
      }

      try {
        const data = JSON.parse(text);
        console.log("✅ Classification appliquée:", data);
        alert(`✅ Classification ${classification} du dataset appliquée avec succès!`);
        
        // APRÈS classification dataset, afficher les colonnes
        console.log("🔄 Appel de initColumnUI pour dataset:", datasetId);
        await initColumnUI(datasetId);
      } catch (e) {
        alert("✅ Opération terminée");
      }

    } catch (err) {
      console.error("💥 Erreur fetch:", err);
      alert("❌ Erreur réseau: " + err.message);
    }
  };
}

/* ----------------------------
   UI COLONNES - SIMPLIFIÉE
----------------------------- */
async function initColumnUI(datasetId) {
  console.log("🔄 DEBUT initColumnUI pour dataset:", datasetId);
  
  const columnSection = document.getElementById("columnClassificationSection");
  const columnsListDiv = document.getElementById("columnsList");
  
  if (!columnSection || !columnsListDiv) {
    console.warn("⚠️ Section colonnes non trouvée dans le DOM");
    return;
  }
  
  try {
    const token = localStorage.getItem("access_token");
    
    // 1. Récupérer les noms de colonnes
    console.log("🔍 Récupération des colonnes pour dataset:", datasetId);
    const columnsRes = await fetch(`${API_URL}/get-columns/${datasetId}`, {
      headers: { "Authorization": `Bearer ${token}` }
    });
    
    if (!columnsRes.ok) {
      throw new Error(`Erreur HTTP ${columnsRes.status}: ${await columnsRes.text()}`);
    }
    
    const columnsData = await columnsRes.json();
    const columnNames = columnsData.columns || [];
    console.log("📊 Colonnes récupérées:", columnNames);
    
    // 2. Récupérer GUIDs depuis localStorage
    const columnGuidsRaw = localStorage.getItem("last_column_guids");
    const columnGuids = JSON.parse(columnGuidsRaw || "{}");
    
    // 3. Récupérer classifications autorisées
    const allowedData = await getAllowedClassifications(datasetId);
    console.log("📊 Classifications autorisées:", allowedData);
    
    // 4. Afficher la section
    columnSection.style.display = "block";
    
    // 5. BOTH PUBLIC AND RESTRICTED can have classified columns
    // No special message for PUBLIC - they can also classify columns
    
    // 6. Afficher les colonnes
    columnsListDiv.innerHTML = "";
    
    if (columnNames.length === 0) {
      columnsListDiv.innerHTML = "<p style='color: #999;'>Aucune colonne disponible</p>";
      return;
    }
    
    // Créer l'interface pour chaque colonne
    columnNames.forEach((colName, index) => {
      const colGuid = columnGuids[colName] || "";
      
      const colDiv = document.createElement("div");
      colDiv.className = "column-item";
      colDiv.style.cssText = `
        background: #f8f9fa;
        border: 1px solid #dee2e6;
        border-radius: 6px;
        padding: 12px;
        margin-bottom: 10px;
      `;
      
      colDiv.innerHTML = `
        <div style="margin-bottom: 8px;">
          <strong>${index + 1}. ${colName}</strong>
        </div>
        
        <div style="display: flex; align-items: center; gap: 10px;">
          <select class="column-class-select" 
                  style="flex: 1; padding: 6px; border: 1px solid #ced4da; border-radius: 4px;"
                  data-column="${colName}" 
                  data-guid="${colGuid}">
            <option value="">-- Pas de classification --</option>
            <option value="PII">PII (email, téléphone, nom, etc.)</option>
            <option value="SENSITIVE">Sensible (médicale, financière)</option>
          </select>
          
          <button class="apply-col-btn" 
                  style="padding: 6px 12px; background: #4CAF50; color: white; border: none; border-radius: 4px; cursor: pointer;"
                  data-column="${colName}" 
                  data-guid="${colGuid}"
                  ${!colGuid ? 'disabled style="background: #cccccc;"' : ''}>
            ${colGuid ? 'Appliquer' : 'GUID manquant'}
          </button>
        </div>
        
        <div style="margin-top: 8px; font-size: 12px; display: none;" class="col-status" id="status-${colName.replace(/\s+/g, '-')}">
        </div>
      `;
      
      columnsListDiv.appendChild(colDiv);
    });
    
    // 7. Configurer les événements
    setupColumnEvents(datasetId);
    console.log("✅ UI colonnes créée avec succès");
    
  } catch (error) {
    console.error("❌ Erreur chargement colonnes:", error);
    columnsListDiv.innerHTML = `
      <div style="background: #f8d7da; color: #721c24; padding: 10px; border-radius: 5px;">
        <strong>❌ Erreur lors du chargement des colonnes</strong><br>
        ${error.message}
      </div>
    `;
  }
}

// Configurer les événements des colonnes
function setupColumnEvents(datasetId) {
  console.log("🔧 Configuration des événements pour les colonnes");
  
  document.querySelectorAll(".apply-col-btn").forEach(btn => {
    btn.addEventListener("click", async function() {
      const columnName = this.dataset.column;
      const columnGuid = this.dataset.guid;
      const select = this.parentElement.querySelector(".column-class-select");
      const classification = select.value;
      const statusDiv = document.getElementById(`status-${columnName.replace(/\s+/g, '-')}`);
      
      if (!classification) {
        alert(`❌ Veuillez sélectionner une classification pour "${columnName}"`);
        return;
      }
      
      if (!columnGuid) {
        alert(`❌ GUID manquant pour "${columnName}". Veuillez re-pousser le dataset vers Atlas.`);
        return;
      }
      
      // Mettre à jour l'UI
      this.disabled = true;
      this.innerHTML = "⏳...";
      this.style.background = "#ff9800";
      
      if (statusDiv) {
        statusDiv.style.display = "block";
        statusDiv.innerHTML = `Application en cours...`;
        statusDiv.style.color = "#ff9800";
      }
      
      try {
        const result = await applyColumnClassification(columnName, classification, datasetId, columnGuid);
        
        this.innerHTML = "✅ Appliqué";
        this.style.background = "#28a745";
        
        if (statusDiv) {
          statusDiv.innerHTML = `✅ Classification "${classification}" appliquée`;
          statusDiv.style.color = "#28a745";
        }
        
      } catch (error) {
        this.innerHTML = "❌ Erreur";
        this.style.background = "#dc3545";
        
        if (statusDiv) {
          statusDiv.innerHTML = `❌ Erreur: ${error.message}`;
          statusDiv.style.color = "#dc3545";
        }
        
        setTimeout(() => {
          this.innerHTML = "Appliquer";
          this.style.background = "#4CAF50";
          this.disabled = false;
        }, 3000);
      }
    });
  });
}