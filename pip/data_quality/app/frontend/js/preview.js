const API_URL = "http://localhost:8000";

// 🔒 Protection : empêcher d’ouvrir preview.html sans upload
document.addEventListener("DOMContentLoaded", () => {
    const id = localStorage.getItem("last_uploaded_dataset_id");
    if (!id) {
        alert("Aucun dataset chargé. Commencez par uploader un fichier.");
        window.location.href = "index.html";
    }
});

document.getElementById("previewBtn").addEventListener("click", async () => {
    const n = parseInt(document.getElementById("previewN").value || 100);

    // 🔹 Dataset ID récupéré depuis localStorage
    const dataset_id = localStorage.getItem("last_uploaded_dataset_id");
    if (!dataset_id) return alert("Impossible de retrouver le dataset. Recommencez l'upload.");

    try {
        const token = localStorage.getItem("access_token");
        if (!token) {
            window.location.href = "index.html";
            return;
        }

        // 🔹 Requête preview
        const res = await fetch(`${API_URL}/preview/${dataset_id}?n=${n}`, {
            method: "GET",
            headers: {
                "Authorization": `Bearer ${token}`
            }
        });
        
        if (!res.ok) {
            const errorData = await res.json().catch(() => ({}));
            throw new Error(errorData.detail || "Erreur preview");
        }

        const data = await res.json();
        renderPreviewTable(data);
    } catch (err) {
        console.error(err);
        alert("Impossible d'afficher l'aperçu. Réessayez.");
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

    // ========== NOUVELLE PARTIE : Message + Redirection + Versionning ==========
    // Créer un message d'information
    const infoMsg = document.createElement('div');
    infoMsg.className = 'info-message';
    infoMsg.textContent = 'Aperçu chargé. Redirection vers la description…';
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

    // 🔥 NOUVEAU : Lancer le calcul de signature en arrière-plan
    const datasetId = localStorage.getItem("last_uploaded_dataset_id");
    const token = localStorage.getItem("access_token");
    
    // Lancer la requête sans attendre (fire and forget)
    fetch(`${API_URL}/api/datasets/${datasetId}/compute-signature`, {
        method: 'POST',
        headers: { 
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
        }
    })
    .then(response => {
        // best-effort: pas bloquant
    })
    .catch(error => {
        // non bloquant
    });

    // Redirection automatique vers describe-columns.html
    setTimeout(() => {
        window.location.href = `describe-columns.html?dataset_id=${datasetId}`;
    }, 2000); // 2 secondes de délai pour voir le preview
}
