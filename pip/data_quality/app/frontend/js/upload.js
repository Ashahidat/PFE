const API_URL = "http://localhost:8000";

// Code de débogage pour vérifier le token au chargement de la page
console.log("🔍 Vérification token au chargement...");
const token = localStorage.getItem("access_token");
console.log("🔑 Token dans localStorage:", token ? `${token.substring(0, 20)}...` : "AUCUN TOKEN");

document.getElementById("uploadBtn").addEventListener("click", async () => {
    const file = document.getElementById("csvFile").files[0];
    const statusDiv = document.getElementById("uploadStatus");

    console.log("🟡 Début processus upload...");
    console.log("📄 Fichier sélectionné:", file ? file.name : "Aucun");

    if (!file) {
        console.log("❌ Aucun fichier sélectionné");
        return alert("Choisissez un fichier CSV");
    }

    statusDiv.innerText = "En cours d'exécution...";
    statusDiv.classList.remove("hidden");

    const formData = new FormData();
    formData.append("file", file);

    try {
        const token = localStorage.getItem("access_token");
        console.log("🔑 Token récupéré:", token ? `${token.substring(0, 20)}...` : "Token manquant");

        console.log("🔄 Envoi requête POST /upload...");
        const res = await fetch(`${API_URL}/upload`, {
            method: "POST",
            body: formData,
            headers: {
                "Authorization": `Bearer ${token}`
            }
        });

        console.log(`📊 Réponse HTTP: ${res.status} ${res.statusText}`);
        
        const data = await res.json();
        console.log("📨 Données reçues:", data);

        if (!res.ok) {
            console.error("❌ Erreur serveur:", data);
            throw new Error(data.detail || "Erreur upload");
        }

        // ✔ On sauvegarde dataset_id (opération synchrone)
        localStorage.setItem("last_uploaded_dataset_id", data.dataset_id);

        if (data.columns) {
            window.columns = data.columns;
            console.log("✅ Upload réussi, colonnes:", data.columns);
            statusDiv.innerText = "Fichier uploadé !";

            // ✔ Redirection immédiate et sûre
            console.log("🔀 Redirection vers preview.html");
            window.location.href = "preview.html";

        } else {
            console.warn("⚠️ Colonnes manquantes dans la réponse");
            statusDiv.innerText = "Erreur : colonnes introuvables";
        }
    } catch (err) {
        console.error("💥 Erreur complète:", err);
        statusDiv.innerText = "Erreur upload CSV";
    }
});
