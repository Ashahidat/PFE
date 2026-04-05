const API_URL = "http://localhost:8000";
const token = localStorage.getItem("access_token");

if (!token) {
    window.location.href = "index.html";
}

let glossaries = [];
let terms = [];
let datasets = [];
let columns = [];
let categories = [];

function escapeHtml(str) {
    if (!str) return "";
    return str.replace(/[&<>]/g, (m) => {
        if (m === "&") return "&amp;";
        if (m === "<") return "&lt;";
        if (m === ">") return "&gt;";
        return m;
    });
}

// ✅ FIX ICI
function refreshTermOptions(categoryId = "") {
    const select = document.getElementById("termAssignSelect");
    if (!select) return;

    const filtered = categoryId
        ? terms.filter((t) => String(t.category_id) === String(categoryId))
        : terms;

    if (!filtered.length) {
        select.innerHTML = "<option value=''>Aucun terme disponible</option>";
        return;
    }

    // 👉 plus de (category)
    select.innerHTML = filtered
        .map(
            (t) =>
                `<option value="${t.id}">${escapeHtml(t.term)}</option>`
        )
        .join("");
}

async function loadCategories() {
    try {
        const res = await fetch(`${API_URL}/glossary/categories`, {
            headers: { Authorization: `Bearer ${token}` },
        });
        if (!res.ok) {
            categories = [];
            refreshCategoryFilter();
            return;
        }
        categories = await res.json();
        refreshCategoryFilter();
        refreshTermOptions(document.getElementById("categoryFilterSelect")?.value || "");
    } catch (err) {
        console.warn("Impossible de charger les catégories", err);
        categories = [];
        refreshCategoryFilter();
        refreshTermOptions(document.getElementById("categoryFilterSelect")?.value || "");
    }
}

function refreshCategoryFilter() {
    const select = document.getElementById("categoryFilterSelect");
    if (!select) return;

    const baseOption = "<option value=''>Toutes catégories</option>";

    select.innerHTML =
        baseOption +
        categories
            .map((cat) => {
                const glossary = glossaries.find(
                    (g) => String(g.id) === String(cat.glossary_id)
                );

                const label = glossary
                    ? `${cat.name} (${glossary.name})`
                    : cat.name;

                return `<option value="${cat.id}">${escapeHtml(label)}</option>`;
            })
            .join("");
}

async function init() {
    await Promise.all([
        loadGlossaries(),
        loadTerms(),
        loadDatasets(),
        loadCategories(),
    ]);

    document
        .getElementById("assignBtn")
        .addEventListener("click", assignTerm);

    document
        .getElementById("datasetSelect")
        .addEventListener("change", (event) => {
            const datasetId = event.target.value;
            if (datasetId) {
                refreshColumns(datasetId);
                refreshAssignments(datasetId);
            }
        });

    const categoryFilter = document.getElementById("categoryFilterSelect");

    if (categoryFilter) {
        categoryFilter.addEventListener("change", (event) => {
            refreshTermOptions(event.target.value);
        });
    }
}

async function loadGlossaries() {
    try {
        const res = await fetch(`${API_URL}/glossary/glossaries`, {
            headers: { Authorization: `Bearer ${token}` },
        });
        glossaries = await res.json();
    } catch (err) {
        console.warn("Impossible de charger les glossaires", err);
    }
}

async function loadTerms() {
    const res = await fetch(`${API_URL}/glossary/terms`, {
        headers: { Authorization: `Bearer ${token}` },
    });

    if (!res.ok) return;

    const data = await res.json();
    terms = data;

    refreshTermOptions(); // ✅ important
}

async function loadDatasets() {
    const res = await fetch(`${API_URL}/glossary/datasets`, {
        headers: { Authorization: `Bearer ${token}` },
    });

    if (!res.ok) return;

    datasets = await res.json();

    const select = document.getElementById("datasetSelect");

    select.innerHTML = datasets
        .map((ds) => `<option value="${ds.id}">${escapeHtml(ds.name)}</option>`)
        .join("");

    if (datasets.length) {
        const datasetId = datasets[0].id;
        refreshColumns(datasetId);
        refreshAssignments(datasetId);
    } else {
        document.getElementById("assignedList").innerHTML =
            "<p>Aucun dataset disponible</p>";
    }
}

async function refreshColumns(datasetId) {
    try {
        const res = await fetch(
            `${API_URL}/upload/get-columns/${datasetId}`,
            {
                headers: { Authorization: `Bearer ${token}` },
            }
        );

        if (!res.ok) throw new Error("Colonnes indisponibles");

        const payload = await res.json();
        columns = payload.columns || [];

        const columnSelect = document.getElementById("columnSelect");

        columnSelect.innerHTML =
            "<option value=''>Dataset entier</option>" +
            columns
                .map(
                    (name) =>
                        `<option value="${name}">${escapeHtml(name)}</option>`
                )
                .join("");
    } catch (err) {
        columns = [];
        document.getElementById("columnSelect").innerHTML =
            "<option value=''>Dataset entier</option>";
    }
}

async function assignTerm() {
    const datasetId = document.getElementById("datasetSelect").value;
    const termId = document.getElementById("termAssignSelect").value;
    const columnName =
        document.getElementById("columnSelect").value || null;

    const status = document.getElementById("assignStatus");

    if (!datasetId || !termId) {
        status.innerText = "Sélectionnez dataset + terme";
        status.style.color = "red";
        return;
    }

    try {
        const res = await fetch(
            `${API_URL}/glossary/datasets/${datasetId}/terms`,
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    Authorization: `Bearer ${token}`,
                },
                body: JSON.stringify({
                    term_id: termId,
                    column_name: columnName,
                }),
            }
        );

        if (!res.ok) {
            const err = await res.json();
            status.innerText = "❌ " + (err.detail || "Erreur");
            status.style.color = "red";
            return;
        }

        status.innerText = "✅ Term assigné";
        status.style.color = "green";

        refreshAssignments(datasetId);
    } catch (err) {
        status.innerText = "❌ Erreur réseau";
        status.style.color = "red";
    }
}

async function refreshAssignments(datasetId) {
    try {
        const res = await fetch(
            `${API_URL}/glossary/datasets/${datasetId}/terms`,
            {
                headers: { Authorization: `Bearer ${token}` },
            }
        );

        if (!res.ok)
            throw new Error("Impossible de lire les assignations");

        const assignments = await res.json();

        const container = document.getElementById("assignedList");

        if (!assignments.length) {
            container.innerHTML = "<p>Aucun terme assigné</p>";
            return;
        }

        container.innerHTML = assignments
            .map(
                (a) => `
                <div class="term-item">
                    <div>
                        <strong>${escapeHtml(a.term)}</strong>
                        <p style="margin:4px 0;">
                            Glossaire : ${escapeHtml(a.glossary_name || "")}<br>
                            Catégorie : ${escapeHtml(a.category || "—")} · Colonne : ${escapeHtml(a.column_name || "entier")}
                        </p>
                    </div>
                    <button class="btn-delete" onclick="removeAssignment('${datasetId}', ${a.glossary_term_id}, '${a.column_name || ""}')">Retirer</button>
                </div>`
            )
            .join("");
    } catch (err) {
        document.getElementById("assignedList").innerHTML =
            "<p style='color:red;'>Impossible de charger les assignations</p>";
    }
}

window.removeAssignment = async function (
    datasetId,
    termId,
    columnName
) {
    try {
        const url = new URL(
            `${API_URL}/glossary/datasets/${datasetId}/terms/${termId}`
        );

        if (columnName) {
            url.searchParams.append("column_name", columnName);
        }

        await fetch(url.toString(), {
            method: "DELETE",
            headers: { Authorization: `Bearer ${token}` },
        });

        refreshAssignments(datasetId);
    } catch (err) {
        console.error("Erreur suppression assignation:", err);
    }
};

init();
