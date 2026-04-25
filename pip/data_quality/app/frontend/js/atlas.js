if (typeof API_URL === 'undefined') {
    const API_URL = "http://localhost:8000";
}

console.log("✅ atlas.js chargé");

document.addEventListener("DOMContentLoaded", () => {
  const button = document.getElementById("pushAtlasBtn");
  const statusDiv = document.getElementById("status");

  button.onclick = async function () {
    statusDiv.innerText = "⏳ Envoi vers Atlas...";

    try {
      const token = localStorage.getItem("access_token");
      const dataset_id = localStorage.getItem("last_uploaded_dataset_id");

      if (!dataset_id) {
        statusDiv.innerText = "❌ Aucun dataset disponible pour Atlas.";
        return;
      }

      const res = await fetch(`${API_URL}/push-atlas/${dataset_id}`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` }
      });

      const text = await res.text();

      console.group("PUSH ATLAS - DEBUG");
      console.log("Réponse brute backend:", text);
      console.groupEnd();

      if (!res.ok) {
        console.error("Erreur backend:", text);
        statusDiv.innerHTML = "❌ Impossible de synchroniser le dataset avec Atlas.";
        return;
      }

      let data = {};
      try {
        data = JSON.parse(text);
      } catch (e) {
        console.error("Erreur parsing JSON:", e);
      }

      if (data.message) {
        if (data.message.includes("existe déjà")) {
          statusDiv.innerHTML = `ℹ️ ${data.message}`;
        } else {
          statusDiv.innerHTML = `✅ ${data.message}`;
        }
      } else {
        statusDiv.innerHTML = "✅ Dataset synchronisé avec Atlas.";
      }

      /* ==================================================
         ✅ STOCKER TOUTES LES DONNÉES IMPORTANTES
         ================================================== */

      if (data.dataset_guid) {
        localStorage.setItem("last_atlas_guid", data.dataset_guid);
        console.log("📊 Dataset GUID stocké:", data.dataset_guid);
      }
      
      // ✅ STOCKER LES GUIDs DES COLONNES (CRITIQUE !)
      if (data.column_guids && typeof data.column_guids === 'object') {
        localStorage.setItem("last_column_guids", JSON.stringify(data.column_guids));
        console.log("📊 GUIDs colonnes stockés:", data.column_guids);
      } else {
        console.warn("⚠️ Pas de column_guids dans la réponse:", data);
        localStorage.setItem("last_column_guids", JSON.stringify({}));
      }

      /* ==================================================
         🚀 LOGIQUE STEPPER : PASSAGE À L'ÉTAPE 2
         ================================================== */
      setTimeout(() => {
        // 1. Marquer l'étape 1 comme terminée
        document.getElementById("step1-indicator").classList.remove("active");
        document.getElementById("step1-indicator").classList.add("completed");
        document.getElementById("step1-indicator").querySelector(".step-counter").innerHTML = "✓";
        
        // 2. Cacher l'étape 1
        document.getElementById("step1-content").style.display = "none";

        // 3. Ne plus demander de classification : déjà déterminée à l'upload (dataset_visibility)
        //    et appliquée automatiquement côté backend pendant le push.
        const section = document.getElementById("classificationSection");
        if (section) section.style.display = "none";
        document.getElementById("step2-indicator").classList.remove("active");
        document.getElementById("step2-indicator").classList.add("completed");
        document.getElementById("step2-indicator").querySelector(".step-counter").innerHTML = "✓";

        // 4. Passer directement à l'étape 3 (colonnes)
        const colSection = document.getElementById("columnClassificationSection");
        if (colSection) colSection.style.display = "block";
        document.getElementById("step3-indicator").classList.add("active");

        // 5. Initialiser l'UI colonnes si disponible (définie dans classifications.js)
        if (typeof initColumnUI === "function") {
          initColumnUI(dataset_id);
        } else {
          console.warn("⚠️ initColumnUI introuvable (classifications.js non chargé ?)");
        }
      }, 800); // Petit délai pour laisser le temps de lire "✅ Succès"

    } catch (err) {
      console.error("Erreur JS:", err);
      statusDiv.innerHTML = "❌ Impossible de communiquer avec Atlas.";
    }
  };
});