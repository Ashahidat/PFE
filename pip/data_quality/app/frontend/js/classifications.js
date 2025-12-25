/* ============================
   classifications.js - VERSION AVEC DEBUG
   ============================ */

const API_URL = "http://localhost:8000";

/* ----------------------------
   Définition des attributs
----------------------------- */
const CLASSIFICATION_ATTRIBUTES = {
  PUBLIC: [],
  INTERNAL: [],
  CONFIDENTIAL: ["level"],
  PII: ["type"]
};

/* ----------------------------
   UI dynamique
----------------------------- */
document.addEventListener("DOMContentLoaded", () => {
  console.log("✅ classifications.js chargé");
  
  const select = document.getElementById("classificationSelect");
  const container = document.getElementById("attributesContainer");
  const applyBtn = document.getElementById("applyClassificationBtn");

  if (!select) {
    console.error("❌ Élément #classificationSelect introuvable");
    return;
  }
  if (!applyBtn) {
    console.error("❌ Élément #applyClassificationBtn introuvable");
    return;
  }

  console.log("✅ Éléments DOM trouvés");

  select.onchange = () => {
    console.log("📝 Sélection changée:", select.value);
    container.innerHTML = "";

    const attrs = CLASSIFICATION_ATTRIBUTES[select.value] || [];
    console.log("📋 Attributs nécessaires:", attrs);

    attrs.forEach(attr => {
      const input = document.createElement("input");
      input.placeholder = attr;
      input.dataset.attr = attr;
      input.style.display = "block";
      input.style.marginBottom = "6px";
      input.className = "attr-input";
      container.appendChild(input);
    });
  };

  /* ----------------------------
     Apply classification
  ----------------------------- */
  applyBtn.onclick = async () => {
    console.log("🔄 Début application classification...");
    
    const token = localStorage.getItem("access_token");
    const datasetId = localStorage.getItem("last_uploaded_dataset_id");
    const atlasGuid = localStorage.getItem("last_atlas_guid");

    console.log("🔍 Données récupérées:", {
      token: token ? "présent" : "absent",
      datasetId,
      atlasGuid
    });

    if (!datasetId) {
      alert("❌ Dataset ID manquant. Veuillez d'abord uploader un dataset.");
      console.error("Dataset ID manquant dans localStorage");
      return;
    }
    if (!atlasGuid) {
      alert("❌ Atlas GUID manquant. Veuillez d'abord pousser vers Atlas.");
      console.error("Atlas GUID manquant dans localStorage");
      return;
    }

    const classification = select.value;
    if (!classification) {
      alert("❌ Choisis une classification.");
      console.error("Classification non sélectionnée");
      return;
    }

    // Collecter les attributs
    const attributes = {};
    container.querySelectorAll(".attr-input").forEach(i => {
      if (i.value.trim()) {
        attributes[i.dataset.attr] = i.value.trim();
      }
    });
    
    console.log("📤 Payload à envoyer:", {
      entity_type: "DATASET",
      entity_id: datasetId,
      atlas_guid: atlasGuid,
      classification_name: classification,
      attributes: Object.keys(attributes).length ? attributes : null
    });

    try {
      const res = await fetch(`${API_URL}/apply-classification`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({
          entity_type: "DATASET",
          entity_id: datasetId,
          atlas_guid: atlasGuid,
          classification_name: classification,
          attributes: Object.keys(attributes).length ? attributes : null
        })
      });

      console.log("📨 Réponse du serveur:", {
        status: res.status,
        statusText: res.statusText
      });

      const text = await res.text();
      console.log("📝 Contenu de la réponse:", text);

      if (!res.ok) {
        console.error("❌ Erreur serveur:", text);
        alert("❌ Erreur classification\n" + text);
        return;
      }

      try {
        const data = JSON.parse(text);
        console.log("✅ Classification appliquée:", data);
        alert("✅ Classification appliquée avec succès!");
      } catch (e) {
        console.log("⚠️ Réponse non-JSON:", text);
        alert("✅ Opération terminée");
      }

    } catch (err) {
      console.error("💥 Erreur fetch:", err);
      alert("❌ Erreur réseau: " + err.message);
    }
  };
});