const API_URL = "http://localhost:8000";

// Au chargement de la page, vérifier si un admin existe
async function checkAdminExists() {
    try {
        const res = await fetch(`${API_URL}/users/count-admin`);
        const data = await res.json();
        const infoMessage = document.getElementById("infoMessage");
        
        if (data.admin_exists === false) {
            infoMessage.innerHTML = "🔒 Premier lancement ? Le premier compte créé sera automatiquement ADMIN.";
        } else {
            infoMessage.innerHTML = "🔒 Contactez votre administrateur pour obtenir un accès.";
        }
    } catch (err) {
        console.error("Erreur vérification admin:", err);
        document.getElementById("infoMessage").innerHTML = "🔒 Connexion sécurisée";
    }
}

document.getElementById("loginBtn").addEventListener("click", async () => {
    const employee_id = document.getElementById("employee_id").value;
    const password = document.getElementById("password").value;
    const status = document.getElementById("status");
    status.classList.remove("hidden");

    if (!employee_id || !password) {
        status.innerText = "Veuillez remplir tous les champs.";
        status.className = "error";
        return;
    }

    try {
        const res = await fetch(`${API_URL}/login`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ employee_id, password })
        });

        const data = await res.json();

        if (!res.ok) {
            status.innerText = data.detail || "Identifiants incorrects.";
            status.className = "error";
            return;
        }

        localStorage.setItem("access_token", data.access_token);
        localStorage.setItem("user_role", data.role);
        localStorage.setItem("user_employee_id", data.employee_id);
        localStorage.setItem("username", data.username);
        localStorage.setItem("department", data.department);

        status.innerText = "Connexion réussie ! Redirection...";
        status.className = "success";

        setTimeout(() => {
            if (data.role === "ADMIN") {
                window.location.href = "admin.html";
            } else {
                window.location.href = "projects.html";
            }
        }, 1000);

    } catch (err) {
        status.innerText = "Erreur de connexion au serveur.";
        status.className = "error";
        console.error(err);
    }
});

// Exécuter au chargement
checkAdminExists();