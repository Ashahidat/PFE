const API_URL = "http://localhost:8000";

// ===================== Fonction principale =====================
async function fetchResults() {
    const statusDiv = document.getElementById("status");
    const resultsSection = document.getElementById("resultsSection");

    try {
        const dag_run_id = localStorage.getItem("last_dag_run_id");
        console.log("🔍 DAG Run ID récupéré:", dag_run_id);
        
        if (!dag_run_id) {
            alert("Pas de DAG en cours");
            return;
        }

        // Test direct : récupérer les résultats sans attendre
        const token = localStorage.getItem("access_token");
        console.log("🔍 Test direct de l'API results...");
        const testRes = await fetch(`${API_URL}/results/${dag_run_id}`, {
            headers: { "Authorization": `Bearer ${token}` }
        });
        const testData = await testRes.json();
        console.log("🔍 Test direct - résultats:", testData);
        
        if (testData && testData.length > 0) {
            console.log("✅ Les résultats existent déjà !");
            renderSummary(testData);
            renderResultsJSON(testData);
            statusDiv.style.display = "none";
            addPushAtlasButton();
            return;
        }
        
        // Sinon, attendre le DAG...
        statusDiv.innerText = "DAG en cours d'exécution...";
        
        let state = null;
        let attempts = 0;
        const maxAttempts = 80;

        while (state !== "success" && state !== "failed" && attempts < maxAttempts) {
            try {
                console.log(`🔍 Tentative ${attempts + 1}: vérification statut...`);
                const res = await fetch(`${API_URL}/dag-status/${dag_run_id}`, {
                    method: "GET",
                    headers: { "Authorization": `Bearer ${token}` }
                });

                console.log(`📡 Réponse dag-status: ${res.status}`);
                
                if (!res.ok) {
                    console.error(`HTTP error! status: ${res.status}`);
                    const errorText = await res.text();
                    console.error("Corps erreur:", errorText);
                    throw new Error(`HTTP error! status: ${res.status}`);
                }

                const data = await res.json();
                state = data?.state || null;
                console.log(`📊 État du DAG: ${state}`);

                if (state === "running" || !state) {
                    statusDiv.innerText = `DAG en cours d'exécution... (${attempts + 1}/${maxAttempts})`;
                    await new Promise(r => setTimeout(r, 5000));
                    attempts++;
                } else {
                    break;
                }

            } catch (error) {
                console.error("Erreur dans la boucle:", error);
                statusDiv.innerText = "Erreur de connexion au serveur";
                await new Promise(r => setTimeout(r, 5000));
                attempts++;
            }
        }

        if (state === "success") {
            statusDiv.innerText = "DAG terminé, récupération des résultats...";

            const res2 = await fetch(`${API_URL}/results/${dag_run_id}`, {
                method: "GET",
                headers: { "Authorization": `Bearer ${token}` }
            });

            console.log(`📡 Réponse results: ${res2.status}`);
            
            if (!res2.ok) throw new Error(`HTTP error! status: ${res2.status}`);

            const results = await res2.json();
            console.log("📊 Résultats finaux:", results);

            if (!results || results.length === 0) {
                statusDiv.innerText = "Aucun résultat disponible !";
                return;
            }

            renderSummary(results);
            renderResultsJSON(results);
            statusDiv.style.display = "none";
            addPushAtlasButton();

        } else if (state === "failed") {
            statusDiv.innerText = "Le DAG a échoué !";
            resultsSection.style.display = "none";
        } else {
            statusDiv.innerText = "Temps d'attente dépassé.";
            resultsSection.style.display = "none";
        }

    } catch (err) {
        console.error("Erreur globale:", err);
        statusDiv.innerText = "Erreur lors de la récupération";
        resultsSection.style.display = "none";
    }
}
// ===================== RÉSUMÉ =====================
function renderSummary(data) {
    const container = document.querySelector('.container');

    const oldSummary = document.getElementById('summary');
    if (oldSummary) oldSummary.remove();

    let total = 0, success = 0, failed = 0;

    data.forEach(item => {
        if (item.status) {
            total++;
            const status = item.status.toLowerCase();

            if (status === "réussi") success++;
            else if (status === "échoué") failed++;
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
        Total tests : ${total} | 
        Réussis : ${success} | 
        Échoués : ${failed} | 
        Taux : ${total ? ((success/total)*100).toFixed(1)+'%' : 'N/A'}
    `;

    container.insertBefore(summaryDiv, container.firstChild.nextSibling);
}

// ===================== CARTES =====================
function renderResultsJSON(data) {
    const resultsSection = document.getElementById("resultsSection");
    resultsSection.innerHTML = "";

    function createCard(item) {
        const statusValue = item.status?.toLowerCase();

        const card = document.createElement("div");
        card.className = "result-card";
        if (statusValue === "réussi") card.classList.add("card-success");
        else if (statusValue === "échoué") card.classList.add("card-failed");

        // Header
        const header = document.createElement("div");
        header.className = "header";
        const title = document.createElement("div");
        title.className = "card-title";
        title.innerText = item.rule_type || "Test";
        const status = document.createElement("div");
        status.className = statusValue === "réussi" ? "status status-success" :
                           statusValue === "échoué" ? "status status-failed" :
                           "status status-running";
        status.innerText = item.status || "N/A";
        header.append(title, status);
        card.appendChild(header);

        // Info
        const infoDiv = document.createElement("div");
        infoDiv.className = "card-info";
        Object.entries(item).forEach(([key, val]) => {
            if (["rule_type","status","examples"].includes(key)) return;
            if (val !== undefined && val !== null) {
                const infoRow = document.createElement("div");
                infoRow.className = "info-row";
                const keySpan = document.createElement("span");
                keySpan.className = "info-key";
                keySpan.textContent = key + ":";
                const valueSpan = document.createElement("span");
                valueSpan.className = "info-value";
                valueSpan.textContent = val;
                infoRow.append(keySpan, valueSpan);
                infoDiv.appendChild(infoRow);
            }
        });
        card.appendChild(infoDiv);

        // Exemples d'erreurs en bas
        if (statusValue === "échoué" && Array.isArray(item.examples) && item.examples.length > 0) {
            const exampleDiv = document.createElement("div");
            exampleDiv.className = "examples-section";
            const title = document.createElement("h4");
            title.innerText = "Exemples d'erreurs";
            exampleDiv.appendChild(title);
            item.examples.forEach(ex => {
                const exItem = document.createElement("div");
                exItem.className = "simple-example";
                exItem.innerText = JSON.stringify(ex);
                exampleDiv.appendChild(exItem);
            });
            card.appendChild(exampleDiv); // ← maintenant après toutes les infos
        }

        resultsSection.appendChild(card);
    }

    if (Array.isArray(data)) {
        data.forEach(item => createCard(item));
    }
}

// ===================== BOUTON =====================
function addPushAtlasButton() {
    if (document.getElementById('pushAtlasBtn')) return;

    const container = document.querySelector('.container');
    const pushButton = document.createElement('button');
    pushButton.id = 'pushAtlasBtn';
    pushButton.className = 'back-button';
    pushButton.textContent = '📤 Passer à Atlas';

    pushButton.onclick = () => window.location.href = "atlas.html";

    container.appendChild(pushButton);
}

document.addEventListener('DOMContentLoaded', fetchResults);
