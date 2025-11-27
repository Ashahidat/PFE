const API_URL = "http://localhost:8000"; 
window.columns = []; // initialisation

// Chargement des colonnes depuis l'API
async function loadColumns() {
    try {
        const res = await fetch(`${API_URL}/get-columns`);
        const data = await res.json();
        if (data.columns && Array.isArray(data.columns)) {
            window.columns = data.columns;
            console.log("Colonnes chargées:", window.columns);
        } else {
            console.warn("Aucune colonne reçue depuis l'API.");
        }
    } catch (err) {
        console.error("Erreur chargement colonnes:", err);
    }
}

// Rendu des colonnes pour duplication sensible
function renderDupColumns() {
    const dupContainer = document.getElementById("dupSensitive-select");
    if (!dupContainer) return;
    dupContainer.innerHTML = "";
    if (!window.columns || !Array.isArray(window.columns)) return;

    window.columns.forEach(col => {
        const div = document.createElement("div");
        div.innerHTML = `<label><input type="checkbox" class="dup-col" value="${col}"> ${col}</label>`;
        dupContainer.appendChild(div);
    });
}

// Rendu des colonnes pour regex
function renderRegexColumns() {
    if (!window.columns || !Array.isArray(window.columns)) return;

    const regexTypes = [
        { id: "regex-email-select", className: "regex-email-col" },
        { id: "regex-phone-select", className: "regex-phone-col" },
        { id: "regex-postal-select", className: "regex-postal-col" }
    ];

    regexTypes.forEach(type => {
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

// Listeners des checkboxes
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

// Lancement du DAG
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

    try {
        const res = await fetch(`${API_URL}/run-dag`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(rules)
        });
        const data = await res.json();
        if (data.dag_run_id) { 
            alert("DAG lancé !");
            localStorage.setItem("dag_run_id", data.dag_run_id);
            window.location.href = "results.html";
        } else {
            console.error(data);
            alert("Erreur lancement DAG");
        }
    } catch (err) {
        console.error(err);
        alert("Erreur lancement DAG");
    }
});

// Initialisation
loadColumns();
