const API_URL = "http://localhost:8000";
const token = localStorage.getItem("access_token");

if (!token) window.location.href = "index.html";

async function loadProfile() {
    const res = await fetch(`${API_URL}/me`, {
        headers: { "Authorization": `Bearer ${token}` }
    });
    const user = await res.json();
    document.getElementById("emp_id").innerText = user.employee_id;
    document.getElementById("username_display").innerText = user.username;
    document.getElementById("department").innerText = user.department;
    document.getElementById("role").innerText = user.role;
}

document.getElementById("updateBtn").addEventListener("click", async () => {
    const username = document.getElementById("new_username").value;
    const password = document.getElementById("new_password").value;
    const body = {};
    if (username) body.username = username;
    if (password) body.password = password;
    
    if (Object.keys(body).length === 0) {
        document.getElementById("status").innerText = "Remplissez au moins un champ";
        return;
    }
    
    const res = await fetch(`${API_URL}/me`, {
        method: "PUT",
        headers: { "Content-Type": "application/json", "Authorization": `Bearer ${token}` },
        body: JSON.stringify(body)
    });
    const data = await res.json();
    if (res.ok) {
        document.getElementById("status").innerText = "✅ Profil mis à jour";
        if (username) localStorage.setItem("username", username);
        loadProfile();
        document.getElementById("new_username").value = "";
        document.getElementById("new_password").value = "";
    } else {
        document.getElementById("status").innerText = data.detail || "Erreur";
    }
});

loadProfile();