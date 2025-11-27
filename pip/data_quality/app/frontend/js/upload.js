const API_URL = "http://localhost:8000";

document.getElementById("uploadBtn").addEventListener("click", async () => {
    const file = document.getElementById("csvFile").files[0];
    const statusDiv = document.getElementById("uploadStatus");

    if (!file) return alert("Choisissez un fichier CSV");

    // Afficher le message avant le fetch
    statusDiv.innerText = "En cours d'exécution...";
    statusDiv.classList.remove("hidden");

    const formData = new FormData();
    formData.append("file", file);

    try {
        const res = await fetch(`${API_URL}/upload`, { method: "POST", body: formData });
        const data = await res.json();

        if (data.columns) {
            window.columns = data.columns; 
            statusDiv.innerText = "Fichier uploadé !";
            // Optionnel : attendre 1s pour que l'utilisateur voie le message
            setTimeout(() => { window.location.href = "preview.html"; }, 1000);
        } else {
            statusDiv.innerText = "Erreur : colonnes introuvables";
        }
    } catch (err) {
        console.error(err);
        statusDiv.innerText = "Erreur upload CSV";
    }
});
