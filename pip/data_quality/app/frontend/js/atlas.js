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
    try { data = JSON.parse(text); } catch {}

    // 🎯 Messages user-friendly
    if (data.message) {
      let friendlyMessage = "";
      if (data.message.includes("créés")) {
        friendlyMessage = `✅ Votre dataset a été ajouté à Atlas avec succès.`;
      } else if (data.message.includes("existe déjà")) {
        friendlyMessage = `ℹ️ Ce dataset existe déjà dans Atlas.`;
      } else {
        friendlyMessage = `✅ ${data.message}`;
      }

      statusDiv.innerHTML = friendlyMessage;
    } else {
      statusDiv.innerHTML = "✅ Dataset synchronisé avec Atlas avec succès.";
    }

  } catch (err) {
    console.error("Erreur JS:", err);
    statusDiv.innerHTML = "❌ Impossible de communiquer avec Atlas.";
  }
};

});
