const API_URL = "http://localhost:8000";

document.getElementById("previewBtn").addEventListener("click", async () => {
    const n = parseInt(document.getElementById("previewN").value || 100);
    console.log(`👀 Demande preview de ${n} lignes`);

    try {
        const token = localStorage.getItem("access_token");
        console.log("🔑 Token preview:", token ? `${token.substring(0, 20)}...` : "Token manquant");

        console.log("🔄 Envoi requête GET /preview...");
        const res = await fetch(`${API_URL}/preview?n=${n}`, {
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
}
