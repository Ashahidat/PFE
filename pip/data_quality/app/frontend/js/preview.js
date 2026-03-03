const API_URL = "http://localhost:8000";

// 🔒 Protection : empêcher d’ouvrir preview.html sans upload
document.addEventListener("DOMContentLoaded", () => {
    const id = localStorage.getItem("last_uploaded_dataset_id");
    if (!id) {
        alert("Aucun dataset chargé. Faites d'abord un upload.");
        window.location.href = "index.html";
    }
});

document.getElementById("previewBtn").addEventListener("click", async () => {
    const n = parseInt(document.getElementById("previewN").value || 100);

    // 🔹 Dataset ID récupéré depuis localStorage
    const dataset_id = localStorage.getItem("last_uploaded_dataset_id");
    if (!dataset_id) return alert("Dataset ID manquant. Faites d'abord un upload !");

    console.log(`👀 Demande preview de ${n} lignes pour dataset ${dataset_id}`);

    try {
        const token = localStorage.getItem("access_token");
        console.log("🔑 Token preview:", token ? `${token.substring(0, 20)}...` : "Token manquant");

        // 🔹 Requête preview
        const res = await fetch(`${API_URL}/preview/${dataset_id}?n=${n}`, {
            method: "GET",
            headers: {
                "Authorization": `Bearer ${token}`
            }
        });

        console.log(`📊 Réponse preview: ${res.status} ${res.statusText}`);
        
        if (!res.ok) {
            const errorData = await res.json();
            console.error("❌ Erreur preview:", errorData);
            throw new Error(errorData.detail || "Erreur preview");
        }

        const data = await res.json();
        console.log(`📊 Données preview reçues: ${data.length} lignes`);

        renderPreviewTable(data);
        console.log("✅ Preview affiché avec succès");
    } catch (err) {
        console.error("💥 Erreur complète preview:", err);
        alert("Erreur preview CSV");
    }
});

function renderPreviewTable(rows) {
    const table = document.getElementById("previewTable");
    table.innerHTML = "";
    if (!rows || rows.length === 0) return;

    const trHead = document.createElement("tr");
    Object.keys(rows[0]).forEach(key => {
        const th = document.createElement("th");
        th.innerText = key;
        trHead.appendChild(th);
    });
    table.appendChild(trHead);

    rows.forEach(row => {
        const tr = document.createElement("tr");
        Object.values(row).forEach(val => {
            const td = document.createElement("td");
            td.innerText = val;
            tr.appendChild(td);
        });
        table.appendChild(tr);
    });

    // ========== NOUVELLE PARTIE : Redirection automatique ==========
    // Créer un message d'information
    const infoMsg = document.createElement('div');
    infoMsg.className = 'info-message';
    infoMsg.textContent = '⏳ Preview chargé ! Redirection vers la description dans 2 secondes...';
    infoMsg.style.cssText = `
        background: #e3f2fd;
        color: #0d47a1;
        padding: 1rem;
        border-radius: 6px;
        margin-top: 1rem;
        text-align: center;
        font-weight: 500;
    `;
    document.querySelector('.container').appendChild(infoMsg);

    // Redirection automatique vers describe-columns.html
    setTimeout(() => {
        const datasetId = localStorage.getItem("last_uploaded_dataset_id");
        console.log(`⏳ Redirection vers describe-columns.html?dataset_id=${datasetId}`);
        window.location.href = `describe-columns.html?dataset_id=${datasetId}`;
    }, 2000); // 2 secondes de délai pour voir le preview
}