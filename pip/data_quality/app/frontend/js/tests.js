const API_URL = "http://localhost:8000";
window.columns = []; // initialisation

// ===================== Chargement des colonnes =====================
async function loadColumns() {
    try {
        const token = localStorage.getItem("access_token");
        const dataset_id = localStorage.getItem("last_uploaded_dataset_id");
        if (!dataset_id) {
            console.error("❌ Aucun dataset_id trouvé dans localStorage");
            return;
        }

        const res = await fetch(`${API_URL}/get-columns/${dataset_id}`, {
            method: "GET",
            headers: { "Authorization": `Bearer ${token}` }
        });

        const data = await res.json();
        if (data.columns && Array.isArray(data.columns)) {
            window.columns = data.columns;
            console.log("📊 Colonnes chargées:", window.columns);
        } else {
            console.warn("⚠️ Aucune colonne reçue depuis l'API.");
        }
    } catch (err) {
        console.error("💥 Erreur chargement colonnes:", err);
    }
}

// ===================== Rendu des colonnes =====================
function renderDupColumns() {
    const container = document.getElementById("dupSensitive-select");
    if (!container) return;
    container.innerHTML = "";
    window.columns.forEach(col => {
        const div = document.createElement("div");
        div.innerHTML = `<label><input type="checkbox" class="dup-col" value="${col}"> ${col}</label>`;
        container.appendChild(div);
    });
}

function renderRegexColumns() {
    const types = [
        { id: "regex-email-select", className: "regex-email-col" },
        { id: "regex-phone-select", className: "regex-phone-col" },
        { id: "regex-postal-select", className: "regex-postal-col" }
    ];
    types.forEach(type => {
        const container = document.getElementById(type.id);
        if (!container) return;
        container.innerHTML = "";
        window.columns.forEach(col => {
            const div = document.createElement("div");
            div.innerHTML = `<label><input type="checkbox" class="${type.className}" value="${col}"> ${col}</label>`;
            container.appendChild(div);
        });
    });
}

// ===================== Listeners =====================
document.getElementById("dupSensitive")?.addEventListener("change", e => {
    const container = document.getElementById("dupSensitive-columns");
    container?.classList.toggle("hidden", !e.target.checked);
    if (e.target.checked) renderDupColumns();
});

document.getElementById("regexTest")?.addEventListener("change", e => {
    const container = document.getElementById("regex-columns");
    container?.classList.toggle("hidden", !e.target.checked);
    if (e.target.checked) renderRegexColumns();
});

// ===================== Lancer le DAG =====================
document.getElementById("runDagBtn")?.addEventListener("click", async () => {
    const rules = {
        duplicates: {
            sensitive: document.getElementById("dupSensitive")?.checked ?
                Array.from(document.querySelectorAll(".dup-col:checked")).map(e => e.value) : [],
            full_row: document.getElementById("dupFull")?.checked || false
        },
        regex: {
            email: document.getElementById("regexTest")?.checked ?
                Array.from(document.querySelectorAll(".regex-email-col:checked")).map(e => e.value) : [],
            phone: document.getElementById("regexTest")?.checked ?
                Array.from(document.querySelectorAll(".regex-phone-col:checked")).map(e => e.value) : [],
            postal_code: document.getElementById("regexTest")?.checked ?
                Array.from(document.querySelectorAll(".regex-postal-col:checked")).map(e => e.value) : []
        }
    };

    const token = localStorage.getItem("access_token");
    const dataset_id = localStorage.getItem("last_uploaded_dataset_id");
    if (!dataset_id) return alert("Impossible de lancer le DAG sans dataset.");

    try {
        const res = await fetch(`${API_URL}/run-dag-v2`, {
            method: "POST",
            headers: { "Content-Type": "application/json", "Authorization": `Bearer ${token}` },
            body: JSON.stringify({ rules, dataset_id })
        });

        const data = await res.json();
        if (data.dag_run_id) {
            localStorage.setItem("last_dag_run_id", data.dag_run_id);
            alert("✅ DAG lancé !");
            window.location.href = "results.html";
        } else {
            console.error(data);
            alert("❌ Erreur lancement DAG");
        }
    } catch (err) {
        console.error(err);
        alert("❌ Erreur lancement DAG");
    }
});

// ===================== Vérifier le statut du DAG =====================
async function checkDagStatus() {
    const dag_run_id = localStorage.getItem("last_dag_run_id");
    if (!dag_run_id) return;

    const token = localStorage.getItem("access_token");
    try {
        const res = await fetch(`${API_URL}/dag-status/${dag_run_id}`, {
            headers: { "Authorization": `Bearer ${token}` }
        });
        const data = await res.json();
        console.log("Etat du DAG :", data.state);
        return data.state;
    } catch (err) {
        console.error("Erreur récupération statut DAG :", err);
    }
}

// ===================== Initialisation =====================
loadColumns();
