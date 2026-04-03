const API_URL = "http://localhost:8000";
const token = localStorage.getItem("access_token");

// Vérification authentification et rôle ADMIN
if (!token || localStorage.getItem("user_role") !== "ADMIN") {
    window.location.href = "login.html";
}

let currentEditEmployeeId = null;

// Charger la liste des utilisateurs
async function loadUsers() {
    try {
        const res = await fetch(`${API_URL}/users`, {
            headers: { "Authorization": `Bearer ${token}` }
        });
        
        if (!res.ok) {
            if (res.status === 401) {
                localStorage.clear();
                window.location.href = "login.html";
            }
            throw new Error("Erreur chargement");
        }
        
        const users = await res.json();
        const container = document.getElementById("usersList");
        container.innerHTML = "";
        
        for (const u of users) {
            const div = document.createElement("div");
            div.className = "user-item";
            
            const roleClass = u.role === 'ADMIN' ? 'admin' : 'data_owner';
            
            div.innerHTML = `
                <div>
                    <strong>${u.employee_id}</strong> - ${u.username} 
                    <span style="color: gray;">(${u.department})</span> 
                    <span class="role-badge ${roleClass}">${u.role}</span>
                </div>
                <div>
                    <button onclick="openEditForm('${u.employee_id}', '${u.username}', '${u.department}', '${u.role}')">✏️ Modifier</button>
                </div>
            `;
            container.appendChild(div);
        }
    } catch (err) {
        console.error("Erreur loadUsers:", err);
        document.getElementById("usersList").innerHTML = '<p style="color: red;">Erreur de chargement</p>';
    }
}

// Ouvrir le formulaire de modification
window.openEditForm = function(empId, username, department, role) {
    currentEditEmployeeId = empId;
    document.getElementById("edit_username").value = username;
    document.getElementById("edit_department").value = department;
    document.getElementById("edit_role").value = role;
    document.getElementById("edit_password").value = "";
    document.getElementById("editForm").classList.add("active");
    document.getElementById("editForm").scrollIntoView({ behavior: "smooth" });
};

// Sauvegarder les modifications
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

// Annuler la modification
document.getElementById("cancelEditBtn").addEventListener("click", () => {
    document.getElementById("editForm").classList.remove("active");
    currentEditEmployeeId = null;
});

// Créer un utilisateur
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

// Déconnexion
document.getElementById("logoutBtn").addEventListener("click", () => {
    localStorage.clear();
    window.location.href = "login.html";
});

// Chargement initial
loadUsers();