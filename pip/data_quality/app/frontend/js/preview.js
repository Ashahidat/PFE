const API_URL = "http://localhost:8000";

document.getElementById("previewBtn").addEventListener("click", async () => {
    const n = parseInt(document.getElementById("previewN").value || 100);
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
