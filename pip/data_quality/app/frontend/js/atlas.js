const API_URL = "http://localhost:8000";

document.addEventListener("DOMContentLoaded", () => {
  const button = document.getElementById("pushAtlasBtn");
  const statusDiv = document.getElementById("status");

  button.onclick = async function() {
    statusDiv.innerText = "⏳ Envoi vers Atlas...";

    try {
      const token = localStorage.getItem("access_token");
      const res = await fetch(`${API_URL}/push-atlas`, {  
        method: "POST",
        headers: { "Authorization": `Bearer ${token}` }
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

      // 🎯 Messages user-friendly - LOGIQUE CORRIGÉE
      if (data.message) {
        // Ajoute juste une icône devant selon le type de message
        if (data.message.includes("existe déjà")) {
          statusDiv.innerHTML = `ℹ️ ${data.message}`;
        } else {
          statusDiv.innerHTML = `✅ ${data.message}`;
        }
      } else {
        statusDiv.innerHTML = "✅ Dataset synchronisé avec Atlas.";
      }

    } catch (err) {
      console.error("Erreur JS:", err);
      statusDiv.innerHTML = "❌ Impossible de communiquer avec Atlas.";
    }
  };
});