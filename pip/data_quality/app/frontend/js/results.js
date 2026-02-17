const API_URL = "http://localhost:8000";

// ===================== Fonction principale =====================
async function fetchResults() {
    const statusDiv = document.getElementById("status");
    const resultsSection = document.getElementById("resultsSection");

    try {
        const dag_run_id = localStorage.getItem("last_dag_run_id");
        if (!dag_run_id) {
            alert("Pas de DAG en cours");
            return;
        }

        statusDiv.innerText = "DAG en cours d'exécution...";

        let state = null;
        let attempts = 0;
        const maxAttempts = 60;

        // ===================== Polling état DAG =====================
        while (state !== "success" && state !== "failed" && attempts < maxAttempts) {
            try {
                const token = localStorage.getItem("access_token");
                const res = await fetch(`${API_URL}/dag-status/${dag_run_id}`, {
                    method: "GET",
                    headers: { "Authorization": `Bearer ${token}` }
                });
                if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
                const data = await res.json();
                state = data?.state || null;

                if (state === "running" || !state) {
                    statusDiv.innerText = `DAG en cours d'exécution... (tentative ${attempts + 1}/${maxAttempts})`;
                    await new Promise(r => setTimeout(r, 5000));
                    attempts++;
                } else {
                    break;
                }
            } catch (error) {
                console.error("Erreur lors de la vérification du statut:", error);
                statusDiv.innerText = "Erreur de connexion au serveur";
                await new Promise(r => setTimeout(r, 5000));
                attempts++;
            }
        }

        if (state === "success") {
            statusDiv.innerText = "DAG terminé avec succès, récupération des résultats...";

            try {
                const token = localStorage.getItem("access_token");
                const res2 = await fetch(`${API_URL}/results/${dag_run_id}`, {
                    method: "GET",
                    headers: { "Authorization": `Bearer ${token}` }
                });
                if (!res2.ok) throw new Error(`HTTP error! status: ${res2.status}`);
                const results = await res2.json();

                if (!results || results.length === 0) {
                    statusDiv.innerText = "Aucun résultat disponible !";
                    return;
                }

                renderSummary(results);
                renderResultsJSON(results);
                statusDiv.style.display = "none";

                addPushAtlasButton();

            } catch (error) {
                console.error("Erreur lors de la récupération des résultats:", error);
                statusDiv.innerText = "Erreur lors de la récupération des résultats";
            }

        } else if (state === "failed") {
            statusDiv.innerText = "Le DAG a échoué !";
            resultsSection.style.display = "none";
        } else {
            statusDiv.innerText = "Impossible de récupérer l'état du DAG dans le temps imparti.";
            resultsSection.style.display = "none";
        }

    } catch (err) {
        console.error("Erreur fetchResults :", err);
        statusDiv.innerText = "Erreur lors de la récupération des résultats";
        resultsSection.style.display = "none";
    }
}

// ===================== Rendu du résumé =====================
function renderSummary(data) {
    const container = document.querySelector('.container');

    const oldSummary = document.getElementById('summary');
    if (oldSummary) oldSummary.remove();

    let total = 0, success = 0, failed = 0;

    data.forEach(item => {
        if (item.status) {
            total++;
            if (item.status.toUpperCase() === 'PASS') success++;
            else if (item.status.toUpperCase() === 'FAIL') failed++;
        }
    });

    const summaryDiv = document.createElement('div');
    summaryDiv.id = 'summary';
    summaryDiv.style.margin = '15px 0 25px 0';
    summaryDiv.style.padding = '12px';
    summaryDiv.style.borderRadius = '8px';
    summaryDiv.style.textAlign = 'center';
    summaryDiv.style.fontWeight = 'bold';
    summaryDiv.style.color = '#fff';
    summaryDiv.style.fontSize = '16px';
    summaryDiv.style.backgroundColor = failed > 0 ? '#e74c3c' : '#27ae60';

    summaryDiv.innerHTML = `
        Résumé du rapport : Total tests : ${total} | Réussis : ${success} | Échoués : ${failed} | Taux de réussite : ${total ? ((success/total)*100).toFixed(1)+'%' : 'N/A'}
    `;

    const h1 = container.querySelector('h1');
    if (h1) h1.insertAdjacentElement('afterend', summaryDiv);
    else container.insertBefore(summaryDiv, container.firstChild);
}

// ===================== Rendu des résultats détaillés =====================
function renderResultsJSON(data) {
    const resultsSection = document.getElementById("resultsSection");
    resultsSection.innerHTML = "";

    function createCard(item) {
        const card = document.createElement("div");
        card.className = "result-card";

        const header = document.createElement("div");
        header.className = "header";

        const title = document.createElement("div");
        title.className = "card-title";
        title.innerText = item.rule_type || "Test de validation";

        const status = document.createElement("div");
        status.className = "status " +
            (item.status?.toUpperCase() === "PASS" ? "status-success" :
             item.status?.toUpperCase() === "FAIL" ? "status-failed" : "status-running");
        status.innerText = item.status || "N/A";

        header.appendChild(title);
        header.appendChild(status);
        card.appendChild(header);

        const infoDiv = document.createElement("div");
        infoDiv.className = "card-info";

        const keysToSkip = ["exemples", "rule_type", "status"];
        Object.entries(item).forEach(([key, val]) => {
            if (!keysToSkip.includes(key) && val !== undefined && val !== null) {
                const infoRow = document.createElement("div");
                infoRow.className = "info-row";

                const keySpan = document.createElement("span");
                keySpan.className = "info-key";
                keySpan.textContent = key + ":";

                const valueSpan = document.createElement("span");
                valueSpan.className = "info-value";
                valueSpan.textContent = typeof val === "object" ? JSON.stringify(val) : val.toString();

                infoRow.appendChild(keySpan);
                infoRow.appendChild(valueSpan);
                infoDiv.appendChild(infoRow);
            }
        });

        card.appendChild(infoDiv);
        resultsSection.appendChild(card);
    }

    if (Array.isArray(data) && data.length > 0) {
        data.forEach(item => createCard(item));
    } else {
        resultsSection.innerHTML = '<div class="no-results">Aucun résultat à afficher</div>';
    }
}


// ===================== Bouton Atlas =====================
function addPushAtlasButton() {
    if (document.getElementById('pushAtlasBtn')) return;

    const container = document.querySelector('.container');
    const pushButton = document.createElement('button');
    pushButton.id = 'pushAtlasBtn';
    pushButton.className = 'back-button';
    pushButton.textContent = '📤 Passer à Atlas';

    pushButton.onclick = function() {
        window.location.href = "atlas.html";
    };

    container.appendChild(pushButton);
}

// ===================== Initialisation =====================
document.addEventListener('DOMContentLoaded', function() {
    console.log("Démarrage de la récupération des résultats...");
    fetchResults();
});
