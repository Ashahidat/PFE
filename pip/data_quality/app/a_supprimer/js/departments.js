const API_URL = window.API_URL || window.location.origin;
const token = localStorage.getItem("access_token");
const viewerRole = localStorage.getItem("user_role");

if (!token || viewerRole !== "SUPER_ADMIN") {
    window.location.href = "index.html";
}

let departmentsCache = [];

function escapeHtml(value) {
    if (value === null || value === undefined) return "";
    return String(value).replace(/[&<>"']/g, (char) => {
        return {
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            '"': "&quot;",
            "'": "&#39;"
        }[char];
    });
}

function departmentOptions(selectedCode) {
    const normalized = selectedCode ? String(selectedCode) : "";
    if (!departmentsCache.length) {
        return `<option value="">Aucun département</option>`;
    }
    return departmentsCache
        .map((d) => {
            const code = d.code;
            const selected = normalized && String(code) === normalized ? " selected" : "";
            return `<option value="${escapeHtml(code)}"${selected}>${escapeHtml(d.label)} (${escapeHtml(code)})</option>`;
        })
        .join("");
}

async function loadDepartments() {
    const status = document.getElementById("deptStatus");
    if (status) status.textContent = "Chargement...";
    try {
        const res = await fetch(`${API_URL}/departments?include_inactive=true`, {
            headers: { Authorization: `Bearer ${token}` },
        });
        if (!res.ok) throw new Error("Erreur chargement départements");
        const data = await res.json();
        departmentsCache = Array.isArray(data) ? data : [];

        const scopeDeptSelect = document.getElementById("scope_dept");
        if (scopeDeptSelect) scopeDeptSelect.innerHTML = departmentOptions("");

        renderDepartments();
        if (status) status.textContent = "";
    } catch (err) {
        console.error(err);
        if (status) status.textContent = "Erreur de chargement";
    }
}

function renderDepartments() {
    const container = document.getElementById("departmentsList");
    if (!container) return;
    if (!departmentsCache.length) {
        container.innerHTML = "<p>Aucun département.</p>";
        return;
    }
    container.innerHTML = `
        <div style="display:flex;flex-direction:column;gap:8px;">
            ${departmentsCache
                .map((d) => {
                    const badge = d.is_active
                        ? '<span style="background:#28a745;color:#fff;padding:2px 8px;border-radius:12px;font-size:12px;">Actif</span>'
                        : '<span style="background:#6c757d;color:#fff;padding:2px 8px;border-radius:12px;font-size:12px;">Inactif</span>';
                    const toggleLabel = d.is_active ? "Désactiver" : "Activer";
                    return `
                        <div style="display:flex;align-items:center;justify-content:space-between;border:1px solid #eee;padding:10px;border-radius:10px;background:#fff;">
                            <div>
                                <strong>${escapeHtml(d.label)}</strong>
                                <span style="color:#666;">(${escapeHtml(d.code)})</span>
                                ${badge}
                            </div>
                            <div style="display:flex;gap:6px;flex-wrap:wrap;">
                                <button onclick="toggleDepartment('${escapeHtml(d.code)}', ${!d.is_active})">${toggleLabel}</button>
                            </div>
                        </div>
                    `;
                })
                .join("")}
        </div>
    `;
}

window.toggleDepartment = async function (code, nextActive) {
    try {
        const res = await fetch(`${API_URL}/departments/${encodeURIComponent(code)}`, {
            method: "PUT",
            headers: {
                "Content-Type": "application/json",
                Authorization: `Bearer ${token}`,
            },
            body: JSON.stringify({ is_active: !!nextActive }),
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: "Erreur" }));
            alert("❌ " + (err.detail || "Erreur"));
            return;
        }
        await loadDepartments();
    } catch (err) {
        console.error(err);
        alert("❌ Erreur réseau");
    }
};

document.getElementById("createDeptBtn")?.addEventListener("click", async () => {
    const code = (document.getElementById("dept_code")?.value || "").trim();
    const label = (document.getElementById("dept_label")?.value || "").trim();
    if (!code || !label) {
        alert("Code et libellé obligatoires");
        return;
    }
    try {
        const res = await fetch(`${API_URL}/departments`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                Authorization: `Bearer ${token}`,
            },
            body: JSON.stringify({ code, label, is_active: true }),
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: "Erreur" }));
            alert("❌ " + (err.detail || "Erreur"));
            return;
        }
        document.getElementById("dept_code").value = "";
        document.getElementById("dept_label").value = "";
        await loadDepartments();
    } catch (err) {
        console.error(err);
        alert("❌ Erreur réseau");
    }
});

async function loadScopesForEmployee(employeeId) {
    const container = document.getElementById("scopesList");
    if (!container) return;
    const trimmed = (employeeId || "").trim();
    if (!trimmed) {
        container.innerHTML = "";
        return;
    }
    container.innerHTML = "<p>Chargement périmètres...</p>";
    try {
        const res = await fetch(`${API_URL}/departments/scopes/${encodeURIComponent(trimmed)}`, {
            headers: { Authorization: `Bearer ${token}` },
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: "Erreur" }));
            container.innerHTML = `<p style="color:red;">${escapeHtml(err.detail || "Erreur")}</p>`;
            return;
        }
        const scopes = await res.json();
        if (!Array.isArray(scopes) || scopes.length === 0) {
            container.innerHTML = "<p>Aucun périmètre.</p>";
            return;
        }
        container.innerHTML = `
            <div style="display:flex;flex-wrap:wrap;gap:6px;">
                ${scopes
                    .map((d) => `<span class="badge" style="background:#eef;border:1px solid #dde;">${escapeHtml(d.label)} (${escapeHtml(d.code)})</span>`)
                    .join("")}
            </div>
        `;
    } catch (err) {
        console.error(err);
        container.innerHTML = "<p style='color:red;'>Erreur réseau</p>";
    }
}

document.getElementById("scope_emp")?.addEventListener("input", (e) => {
    loadScopesForEmployee(e.target.value);
});

document.getElementById("grantScopeBtn")?.addEventListener("click", async () => {
    const employeeId = (document.getElementById("scope_emp")?.value || "").trim();
    const dept = document.getElementById("scope_dept")?.value || "";
    if (!employeeId || !dept) {
        alert("Employee ID et département requis");
        return;
    }
    try {
        const res = await fetch(`${API_URL}/departments/scopes`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                Authorization: `Bearer ${token}`,
            },
            body: JSON.stringify({ employee_id: employeeId, department_code: dept }),
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: "Erreur" }));
            alert("❌ " + (err.detail || "Erreur"));
            return;
        }
        await loadScopesForEmployee(employeeId);
    } catch (err) {
        console.error(err);
        alert("❌ Erreur réseau");
    }
});

document.getElementById("revokeScopeBtn")?.addEventListener("click", async () => {
    const employeeId = (document.getElementById("scope_emp")?.value || "").trim();
    const dept = document.getElementById("scope_dept")?.value || "";
    if (!employeeId || !dept) {
        alert("Employee ID et département requis");
        return;
    }
    try {
        const res = await fetch(`${API_URL}/departments/scopes`, {
            method: "DELETE",
            headers: {
                "Content-Type": "application/json",
                Authorization: `Bearer ${token}`,
            },
            body: JSON.stringify({ employee_id: employeeId, department_code: dept }),
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: "Erreur" }));
            alert("❌ " + (err.detail || "Erreur"));
            return;
        }
        await loadScopesForEmployee(employeeId);
    } catch (err) {
        console.error(err);
        alert("❌ Erreur réseau");
    }
});

loadDepartments();
