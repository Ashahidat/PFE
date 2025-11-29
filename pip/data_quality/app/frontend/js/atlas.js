const API_URL = "http://localhost:8000";

document.addEventListener("DOMContentLoaded", () => {
  const button = document.getElementById("pushAtlasBtn");
  const statusDiv = document.getElementById("status");

  button.onclick = async function() {
    statusDiv.innerText = "⏳ Envoi vers Atlas...";

    try {
      const res = await fetch(`${API_URL}/push-atlas`, { method: "POST" });

      const text = await res.text();

      // 🔍 Tous les logs en console (non visibles pour l'utilisateur)
      console.group("PUSH ATLAS - DEBUG");
      console.log("Réponse brute backend:", text);
      console.groupEnd();

      if (!res.ok) {
        console.error("Erreur backend:", text);
        statusDiv.innerHTML = "❌ Échec du push vers Atlas";
        return;
      }

      // Parse JSON si possible
      let data = {};
      try { data = JSON.parse(text); } catch {}

      // ✔️ UI minimaliste
      statusDiv.innerHTML =  `✅ Dataset envoyé vers Atlas avec succès !`;
      console.log("Dataset GUID:", data.dataset_guid);


    } catch (err) {
      console.error("Erreur JS:", err);
      statusDiv.innerHTML = "❌ Erreur lors de la communication avec Atlas";
    }
  };
});
