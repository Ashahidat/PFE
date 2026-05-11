const API_URL = window.API_URL || window.location.origin;

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

    const datasetId = localStorage.getItem("last_uploaded_dataset_id");
    const token = localStorage.getItem("access_token");

    // 🔥 Lancer le calcul de signature en arrière-plan (non bloquant)
    fetch(`${API_URL}/api/datasets/${datasetId}/compute-signature`, {
        method: 'POST',
        headers: { 
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
        }
    }).catch(() => { /* best-effort */ });

    // ========== NOUVELLE PARTIE : Bouton de passage à l'étape suivante ==========
    
    // Éviter de dupliquer le bouton si l'utilisateur clique plusieurs fois sur "Voir"
    let actionContainer = document.getElementById('next-step-container');
    if (!actionContainer) {
        actionContainer = document.createElement('div');
        actionContainer.id = 'next-step-container';
        actionContainer.style.cssText = `
            margin-top: 25px;
            text-align: right;
            border-top: 1px solid #e5e7eb;
            padding-top: 15px;
        `;
        document.querySelector('.container').appendChild(actionContainer);
    }

    // Mettre à jour le contenu du conteneur avec le bouton
    actionContainer.innerHTML = `
        <button id="goToDescriptionBtn" style="
            background-color: var(--success); 
            font-size: 1.1em; 
            padding: 10px 20px;">
            Valider et passer à la description ➔
        </button>
    `;

    // Ajouter l'événement de redirection au clic
    document.getElementById('goToDescriptionBtn').addEventListener('click', () => {
        window.location.href = `describe-columns.html?dataset_id=${datasetId}`;
    });
}
