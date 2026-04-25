const API_URL = "http://localhost:8000";
const token = localStorage.getItem("access_token");
const viewerRole = localStorage.getItem("user_role");
const allowedRoles = ["SUPER_ADMIN", "ADMIN", "ADMIN_GLOSSAIRE"];
const roleLimitDescriptions = {
    SUPER_ADMIN: "Super-admins",
    ADMIN_GLOSSAIRE: "Admins glossaire"
};
const criticalRoleValues = ["SUPER_ADMIN", "ADMIN_GLOSSAIRE"];

if (viewerRole !== "SUPER_ADMIN") {
    const lockSelect = (selectId) => {
        const select = document.getElementById(selectId);
        if (!select) return;
        Array.from(select.options).forEach((option) => {
            if (criticalRoleValues.includes(option.value)) {
                option.disabled = true;
            }
        });
    };
    lockSelect("role");
    lockSelect("edit_role");
}

if (!token || !allowedRoles.includes(viewerRole)) {
    window.location.href = "index.html";
}

let currentEditEmployeeId = null;
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
    try {
        const res = await fetch(`${API_URL}/departments`, {
            headers: { "Authorization": `Bearer ${token}` }
        });
        if (!res.ok) throw new Error("Erreur chargement départements");
        const depts = await res.json();
        departmentsCache = Array.isArray(depts) ? depts : [];

        const createSelect = document.getElementById("department");
        const editSelect = document.getElementById("edit_department");
        if (createSelect) createSelect.innerHTML = departmentOptions("");
        if (editSelect) editSelect.innerHTML = departmentOptions("");
    } catch (err) {
        console.error(err);
    }
}

async function loadUsers() {
    try {
        const res = await fetch(`${API_URL}/users`, {
            headers: { "Authorization": `Bearer ${token}` }
        });
        
        if (!res.ok) {
            if (res.status === 401) {
                localStorage.clear();
                window.location.href = "index.html";
            }
            throw new Error("Erreur chargement");
        }
        
        const users = await res.json();
        const container = document.getElementById("usersList");
        container.innerHTML = "";
        
        for (const u of users) {
            if (u.employee_id === localStorage.getItem("user_employee_id")) {
                continue;
            }
            
            const div = document.createElement("div");
            div.className = "user-item";
            
            let roleClass = 'data_owner';
            if (u.role === 'ADMIN') roleClass = 'admin';
            else if (u.role === 'AUDIT') roleClass = 'audit';
            else if (u.role === 'SUPER_ADMIN') roleClass = 'super_admin';
            else if (u.role === 'ADMIN_GLOSSAIRE') roleClass = 'admin_glossaire';
            
            const isProtected = u.is_protected === true;
            const isActive = u.is_active !== false; // par défaut true
            const isSuperTarget = u.role === 'SUPER_ADMIN';
            const canInteractWithTarget = (viewerRole === 'SUPER_ADMIN' || !isSuperTarget) && (!isProtected || viewerRole === 'SUPER_ADMIN');
            
            // Badge statut actif/inactif
            const statusBadge = isActive
                ? '<span style="background: #28a745; color: white; padding: 2px 6px; border-radius: 12px; font-size: 10px; margin-left: 5px;">✓ Actif</span>'
                : '<span style="background: #6c757d; color: white; padding: 2px 6px; border-radius: 12px; font-size: 10px; margin-left: 5px;">⛔ Inactif</span>';
            
            const protectedBadge = isProtected 
                ? '<span style="background: #e74c3c; color: white; padding: 2px 6px; border-radius: 12px; font-size: 10px; margin-left: 5px;">🔒 Protégé</span>'
                : '';
            
            // Bouton Modifier (désactivé si protégé)
            const editButton = canInteractWithTarget
                ? `<button onclick="openEditForm('${u.employee_id}', '${u.username}', '${u.department}', '${u.role}', ${isActive})" style="background: #ffc107; border: none; padding: 5px 10px; border-radius: 3px; cursor: pointer;">✏️ Modifier</button>`
                : '<button disabled style="background: gray; cursor: not-allowed; padding: 5px 10px; border-radius: 3px; border: none;">🔒 Protégé</button>';
            
            // Bouton Activer/Désactiver (si non protégé)
            const toggleButton = canInteractWithTarget
                ? (isActive
                    ? `<button onclick="toggleUserStatus('${u.employee_id}', false)" style="background: #dc3545; color: white; border: none; padding: 5px 10px; border-radius: 3px; cursor: pointer; margin-left: 5px;">🔴 Désactiver</button>`
                    : `<button onclick="toggleUserStatus('${u.employee_id}', true)" style="background: #28a745; color: white; border: none; padding: 5px 10px; border-radius: 3px; cursor: pointer; margin-left: 5px;">🟢 Activer</button>`)
                : '';
            
            div.innerHTML = `
                <div>
                    <strong>${u.employee_id}</strong> - ${u.username} 
                    <span style="color: gray;">(${u.department})</span> 
                    <span class="role-badge ${roleClass}">${u.role}</span>
                    ${statusBadge}
                    ${protectedBadge}
                </div>
                <div>
                    ${editButton}
                    ${toggleButton}
                </div>
            `;
            container.appendChild(div);
        }
    } catch (err) {
        console.error("Erreur loadUsers:", err);
        document.getElementById("usersList").innerHTML = '<p style="color: red;">Erreur de chargement</p>';
    }
    loadRoleLimits();
}

async function loadRoleLimits() {
    const container = document.getElementById("roleLimits");
    if (!container) return;
    container.innerHTML = '<div class="role-limit">Chargement...</div>';

    try {
        const res = await fetch(`${API_URL}/users/role-counts`, {
            headers: {
                "Authorization": `Bearer ${token}`
            }
        });

        if (!res.ok) {
            throw new Error("Impossible de charger les quotas");
        }

        const data = await res.json();
        renderRoleLimitPanel(data);
    } catch (err) {
        console.error("Erreur role limits:", err);
        container.innerHTML = '<div class="role-limit reached">Impossible de charger les quotas</div>';
    }
}


function renderRoleLimitPanel(data) {
    const container = document.getElementById("roleLimits");
    if (!container) return;
    if (!Array.isArray(data) || data.length === 0) {
        container.innerHTML = '<div class="role-limit">Aucun quota défini</div>';
        return;
    }

    container.innerHTML = data
        .map((item) => {
            const label = roleLimitDescriptions[item.role] || item.role;
            const count = item.count ?? 0;
            const limit = item.limit ?? 0;
            if (limit <= 0) {
                return `
                    <div class="role-limit">
                        <div>
                            <strong>${label}</strong>
                            <div style="font-size: 12px; color: #555;">${count} actif(s)</div>
                        </div>
                        <small>Pas de limite configurée</small>
                    </div>
                `;
            }
            const reached = count >= limit;
            const statusText = reached ? "Limite atteinte" : `${count}/${limit}`;
            return `
                <div class="role-limit ${reached ? "reached" : ""}">
                    <div>
                        <strong>${label}</strong>
                        <div style="font-size: 12px; color: #555;">${statusText}</div>
                    </div>
                    <small>${reached ? "Aucun créneau libre" : "Capacité disponible"}</small>
                </div>
            `;
        })
        .join("");
}

// Fonction pour activer/désactiver un utilisateur
window.toggleUserStatus = async function(employeeId, activate) {
    const action = activate ? "activer" : "désactiver";
    if (!confirm(`Voulez-vous vraiment ${action} cet utilisateur ?`)) return;
    
    try {
        const res = await fetch(`${API_URL}/users/${employeeId}`, {
            method: "PUT",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${token}`
            },
            body: JSON.stringify({ is_active: activate })
        });
        
        if (res.ok) {
            alert(`✅ Utilisateur ${action} avec succès`);
            loadUsers();
        } else {
            const err = await res.json();
            alert("❌ Erreur: " + (err.detail || "Erreur inconnue"));
        }
    } catch (err) {
        alert("❌ Erreur de connexion");
    }
};

window.openEditForm = function(empId, username, department, role, isActive) {
    currentEditEmployeeId = empId;
    document.getElementById("edit_username").value = username;
    const deptSelect = document.getElementById("edit_department");
    if (deptSelect) {
        deptSelect.innerHTML = departmentOptions(department);
        deptSelect.value = department || "";
    }
    document.getElementById("edit_role").value = role;
    document.getElementById("edit_password").value = "";
    document.getElementById("edit_is_active").value = isActive ? "true" : "false";
    document.getElementById("editForm").classList.add("active");
    document.getElementById("editForm").scrollIntoView({ behavior: "smooth" });
};

document.getElementById("saveEditBtn").addEventListener("click", async () => {
    const body = {};
    const newUsername = document.getElementById("edit_username").value;
    const newDepartment = document.getElementById("edit_department").value;
    const newRole = document.getElementById("edit_role").value;
    const newPassword = document.getElementById("edit_password").value;
    const newIsActive = document.getElementById("edit_is_active").value === "true";
    
    if (newUsername) body.username = newUsername;
    if (newDepartment) body.department = newDepartment;
    if (newRole) body.role = newRole;
    if (newPassword && newPassword !== "") body.password = newPassword;
    body.is_active = newIsActive;
    
    if (Object.keys(body).length === 1 && body.is_active !== undefined) {
        // Seulement le statut actif/inactif change
    } else if (Object.keys(body).length === 0) {
        alert("Aucune modification à enregistrer");
        return;
    }
    
    try {
        const res = await fetch(`${API_URL}/users/${currentEditEmployeeId}`, {
            method: "PUT",
            headers: { 
                "Content-Type": "application/json", 
                "Authorization": `Bearer ${token}` 
            },
            body: JSON.stringify(body)
        });
        
        if (res.ok) {
            alert("✅ Utilisateur modifié avec succès");
            document.getElementById("editForm").classList.remove("active");
            loadUsers();
        } else {
            const err = await res.json();
            alert("❌ Erreur: " + (err.detail || "Erreur inconnue"));
        }
    } catch (err) {
        alert("❌ Erreur de connexion");
    }
});

document.getElementById("cancelEditBtn").addEventListener("click", () => {
    document.getElementById("editForm").classList.remove("active");
    currentEditEmployeeId = null;
});

document.getElementById("createBtn").addEventListener("click", async () => {
    const body = {
        employee_id: document.getElementById("emp_id").value,
        username: document.getElementById("username").value,
        password: document.getElementById("password").value,
        department: document.getElementById("department").value,
        role: document.getElementById("role").value
    };
    
    if (!body.employee_id || !body.username || !body.password || !body.department) {
        alert("Tous les champs sont obligatoires");
        return;
    }
    
    if (!["DATA_OWNER", "ADMIN", "ADMIN_GLOSSAIRE", "SUPER_ADMIN", "AUDIT"].includes(body.role)) {
        alert("Rôle invalide");
        return;
    }
    
    try {
        const res = await fetch(`${API_URL}/users`, {
            method: "POST",
            headers: { 
                "Content-Type": "application/json", 
                "Authorization": `Bearer ${token}` 
            },
            body: JSON.stringify(body)
        });
        
        if (res.ok) {
            alert("✅ Utilisateur créé avec succès");
            document.getElementById("emp_id").value = "";
            document.getElementById("username").value = "";
            document.getElementById("password").value = "";
            document.getElementById("department").value = "";
            loadUsers();
        } else {
            const err = await res.json();
            alert("❌ Erreur: " + (err.detail || "Erreur inconnue"));
        }
    } catch (err) {
        alert("❌ Erreur de connexion");
    }
});

loadDepartments().finally(loadUsers);
