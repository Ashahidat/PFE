const API_URL = "http://localhost:8000";

// ================= DEBUG TOKEN =================
console.log("🔍 Vérification token au chargement...");
const token = localStorage.getItem("access_token");
console.log("🔑 Token dans localStorage:", token ? `${token.substring(0, 20)}...` : "AUCUN TOKEN");

// ================= AFFICHAGE PROJET =================
document.addEventListener("DOMContentLoaded", () => {
    const projectName = localStorage.getItem("current_project_name");
    if (projectName) {
        document.getElementById("currentProjectName").textContent = projectName;
    } else {
        window.location.href = "projects.html"; // Rediriger si pas de projet
    }
});

// ================= UPLOAD CSV =================
document.getElementById("uploadBtn").addEventListener("click", async () => {
    const file = document.getElementById("csvFile").files[0];
    const projectId = localStorage.getItem("current_project_id");
    const description = document.getElementById("description").value; // ✅ Récupérer description
    const statusDiv = document.getElementById("uploadStatus");

    console.log("🟡 Début processus upload...");
    console.log("📄 Fichier sélectionné:", file ? file.name : "Aucun");
    console.log("📁 Projet sélectionné:", projectId);
    console.log("📝 Description:", description);

    // 🔴 Vérifications
    if (!file) {
        console.log("❌ Aucun fichier sélectionné");
        return alert("Choisissez un fichier CSV");
    }

    if (!projectId) {
        console.log("❌ Aucun projet sélectionné");
        return alert("Sélectionnez un projet d'abord");
    }

    statusDiv.innerText = "En cours d'exécution...";
    statusDiv.classList.remove("hidden");

    // ================= FormData =================
    const formData = new FormData();
    formData.append("file", file);
    formData.append("project_id", projectId);
    formData.append("description", description); // ✅ Ajouter description

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

        // ✔ Sauvegarde dataset_id
        localStorage.setItem("last_uploaded_dataset_id", data.dataset_id);

        if (data.columns) {
            window.columns = data.columns;
            console.log("✅ Upload réussi, colonnes:", data.columns);

            statusDiv.innerText = "Fichier uploadé avec succès !";

            // ✔ Redirection
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