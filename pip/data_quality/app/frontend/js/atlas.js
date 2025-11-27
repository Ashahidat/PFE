const API_URL = "http://localhost:8000";

document.addEventListener("DOMContentLoaded", () => {
  const button = document.getElementById("pushAtlasBtn");
  const statusDiv = document.getElementById("status");
  const logs = document.getElementById("logs");

  button.onclick = async function() {
    statusDiv.innerText = "⏳ Envoi vers Atlas...";
    logs.textContent = "";

    try {
      const res = await fetch(`${API_URL}/push-atlas`, { method: "POST" });

      const text = await res.text(); // on loggue même si ce n’est pas JSON
      logs.textContent = "Réponse brute :\n" + text;

      if (!res.ok) {
        throw new Error(`HTTP ${res.status} : ${text}`);
      }

      let data = {};
      try {
        data = JSON.parse(text);
      } catch {
        // ce n'est pas du JSON valide
      }

      statusDiv.innerHTML = `
        ✅ Succès !
        <br>Message: ${data.message || "N/A"}
        <br>DataSet GUID: ${data.dataset_guid || "N/A"}
      `;

    } catch (err) {
      console.error("Erreur push Atlas:", err);
      statusDiv.innerText = "❌ Erreur lors de l'envoi vers Atlas";
      logs.textContent += "\nErreur JS : " + err.message;
    }
  };
});
