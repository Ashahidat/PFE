const API_URL = "http://localhost:8000";
const token = localStorage.getItem("access_token");

if (!token || localStorage.getItem("user_role") !== "ADMIN") {
    window.location.href = "index.html";
}

let currentEditEmployeeId = null;

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
            // Ignorer l'admin connecté lui-même
            if (u.employee_id === localStorage.getItem("user_employee_id")) {
                continue;
            }
            
            const div = document.createElement("div");
            div.className = "user-item";
            const roleClass = u.role === 'ADMIN' ? 'admin' : 'data_owner';
            
            // ✅ Vérifier si l'utilisateur est protégé
            const isProtected = u.is_protected === true;
            
            // Badge protégé
            const protectedBadge = isProtected 
                ? '<span style="background: #e74c3c; color: white; padding: 2px 6px; border-radius: 12px; font-size: 10px; margin-left: 5px;">🔒 Protégé</span>'
                : '';
            
            // Bouton Modifier (désactivé si protégé)
            const editButton = isProtected 
                ? '<button disabled style="background: gray; cursor: not-allowed; padding: 5px 10px; border-radius: 3px; border: none;">🔒 Protégé</button>'
                : `<button onclick="openEditForm('${u.employee_id}', '${u.username}', '${u.department}', '${u.role}')" style="background: #ffc107; border: none; padding: 5px 10px; border-radius: 3px; cursor: pointer;">✏️ Modifier</button>`;
            
            div.innerHTML = `
                <div>
                    <strong>${u.employee_id}</strong> - ${u.username} 
                    <span style="color: gray;">(${u.department})</span> 
                    <span class="role-badge ${roleClass}">${u.role}</span>
                    ${protectedBadge}
                </div>
                <div>
                    ${editButton}
                </div>
            `;
            container.appendChild(div);
        }
    } catch (err) {
        console.error("Erreur loadUsers:", err);
        document.getElementById("usersList").innerHTML = '<p style="color: red;">Erreur de chargement</p>';
    }
}

window.openEditForm = function(empId, username, department, role) {
    currentEditEmployeeId = empId;
    document.getElementById("edit_username").value = username;
    document.getElementById("edit_department").value = department;
    document.getElementById("edit_role").value = role;
    document.getElementById("edit_password").value = "";
    document.getElementById("editForm").classList.add("active");
    document.getElementById("editForm").scrollIntoView({ behavior: "smooth" });
};

document.getElementById("saveEditBtn").addEventListener("click", async () => {
    const body = {};
    const newUsername = document.getElementById("edit_username").value;
    const newDepartment = document.getElementById("edit_department").value;
    const newRole = document.getElementById("edit_role").value;
    const newPassword = document.getElementById("edit_password").value;
    
    if (newUsername) body.username = newUsername;
    if (newDepartment) body.department = newDepartment;
    if (newRole) body.role = newRole;
    if (newPassword && newPassword !== "") body.password = newPassword;
    
    if (Object.keys(body).length === 0) {
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

loadUsers();