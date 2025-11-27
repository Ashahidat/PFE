const API_URL = "http://localhost:8000";

// Upload CSV
document.getElementById("uploadBtn")?.addEventListener("click", async () => {
    const file = document.getElementById("csvFile")?.files[0];
    if (!file) return alert("Choisissez un fichier CSV");

    const formData = new FormData();
    formData.append("file", file);

    try {
        const res = await fetch(`${API_URL}/upload`, { method: "POST", body: formData });
        const data = await res.json();
        if (data.columns) {
            alert("Fichier uploadé !");
            window.columns = data.columns;
            document.getElementById("upload-section")?.classList.add("hidden");
            document.getElementById("preview-section")?.classList.remove("hidden");
            document.getElementById("tests-section")?.classList.remove("hidden");
        }
    } catch (err) { console.error(err); alert("Erreur upload CSV"); }
});

// Preview CSV
document.getElementById("previewBtn")?.addEventListener("click", async () => {
    const n = parseInt(document.getElementById("previewN")?.value || 100);
    try {
        const res = await fetch(`${API_URL}/preview?n=${n}`);
        const data = await res.json();
        renderPreviewTable(data);
    } catch (err) { console.error(err); alert("Erreur preview CSV"); }
});

function renderPreviewTable(rows) {
    const table = document.getElementById("previewTable");
    table.innerHTML = "";
    if (!rows || rows.length === 0) return;

    const trHead = document.createElement("tr");
    Object.keys(rows[0]).forEach(key => { const th = document.createElement("th"); th.innerText = key; trHead.appendChild(th); });
    table.appendChild(trHead);

    rows.forEach(row => {
        const tr = document.createElement("tr");
        Object.values(row).forEach(val => { const td = document.createElement("td"); td.innerText = val; tr.appendChild(td); });
        table.appendChild(tr);
    });
}

// Colonnes dynamiques
document.getElementById("dupSensitive")?.addEventListener("change", e => {
    const container = document.getElementById("dupSensitive-columns");
    container.classList.toggle("hidden", !e.target.checked);
    if (e.target.checked) renderDupColumns();
});
document.getElementById("regexTest")?.addEventListener("change", e => {
    const container = document.getElementById("regex-columns");
    container.classList.toggle("hidden", !e.target.checked);
    if (e.target.checked) renderRegexColumns();
});

function renderDupColumns() {
    const dupContainer = document.getElementById("dupSensitive-select");
    dupContainer.innerHTML = "";
    window.columns.forEach(col => { const div = document.createElement("div"); div.innerHTML = `<label><input type="checkbox" class="dup-col" value="${col}"> ${col}</label>`; dupContainer.appendChild(div); });
}

function renderRegexColumns() {
    const regexTypes = [
        { id: "regex-email-select", className: "regex-email-col" },
        { id: "regex-phone-select", className: "regex-phone-col" },
        { id: "regex-postal-select", className: "regex-postal-col" }
    ];
    regexTypes.forEach(type => {
        const container = document.getElementById(type.id);
        container.innerHTML = "";
        window.columns.forEach(col => {
            const div = document.createElement("div");
            div.innerHTML = `<label><input type="checkbox" class="${type.className}" value="${col}"> ${col}</label>`;
            container.appendChild(div);
        });
    });
}

// Lancer DAG
document.getElementById("runDagBtn")?.addEventListener("click", async () => {
    const rules = {
        duplicates: {
            sensitive: document.getElementById("dupSensitive")?.checked ? Array.from(document.querySelectorAll(".dup-col:checked")).map(e => e.value) : [],
            full_row: document.getElementById("dupFull")?.checked || false
        },
        regex: {
            email: document.getElementById("regexTest")?.checked ? Array.from(document.querySelectorAll(".regex-email-col:checked")).map(e => e.value) : [],
            phone: document.getElementById("regexTest")?.checked ? Array.from(document.querySelectorAll(".regex-phone-col:checked")).map(e => e.value) : [],
            postal_code: document.getElementById("regexTest")?.checked ? Array.from(document.querySelectorAll(".regex-postal-col:checked")).map(e => e.value) : []
        }
    };

    try {
        const res = await fetch(`${API_URL}/run-dag`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(rules) });
        const data = await res.json();
        if (data.dag_run_id) { alert("DAG lancé !"); pollDagStatus(data.dag_run_id); } 
        else { console.error(data); alert("Erreur lancement DAG"); }
    } catch (err) { console.error(err); alert("Erreur lancement DAG"); }
});

// Poll DAG
async function pollDagStatus(dag_run_id) {
    let state = null;
    try {
        while (state !== "success" && state !== "failed") {
            const res = await fetch(`${API_URL}/dag-status?dag_run_id=${dag_run_id}`);
            const data = await res.json();
            state = data.state;
            await new Promise(r => setTimeout(r, 5000));
        }
        fetchResults();
    } catch (err) { console.error(err); alert("Erreur récupération statut DAG"); }
}

// Résultats
async function fetchResults() {
    try {
        const res = await fetch(`${API_URL}/results`);
        const data = await res.json();
        const table = document.getElementById("resultsTable");
        table.innerHTML = "";
        if (!data || data.length === 0) return;

        const trHead = document.createElement("tr");
        Object.keys(data[0]).forEach(key => { const th = document.createElement("th"); th.innerText = key; trHead.appendChild(th); });
        table.appendChild(trHead);

        data.forEach(row => {
            const tr = document.createElement("tr");
            Object.values(row).forEach(val => { const td = document.createElement("td"); td.innerText = val; tr.appendChild(td); });
            table.appendChild(tr);
        });

        document.getElementById("results-section")?.classList.remove("hidden");
    } catch (err) { console.error(err); alert("Erreur récupération résultats"); }
}
