const API_URL = window.API_URL || window.location.origin;

async function readJsonSafely(res) {
    const contentType = (res.headers && res.headers.get && res.headers.get("content-type")) || "";
    if (contentType.includes("application/json")) {
        return await res.json();
    }
    const text = await res.text();
    const preview = text.slice(0, 200).replace(/\s+/g, " ").trim();
    throw new Error(`Réponse non-JSON (${res.status}) : ${preview || "[vide]"}`);
}

// Au chargement de la page, vérifier si un admin existe
async function checkAdminExists() {
    try {
        const res = await fetch(`${API_URL}/users/count-admin`, { credentials: "include" });
        const data = await readJsonSafely(res);
        const infoMessage = document.getElementById("infoMessage");
        
        if (data.admin_exists === false) {
            infoMessage.innerHTML = "🔒 Premier lancement ? Le premier compte créé sera automatiquement SUPER_ADMIN et pourra gérer les comptes.";
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
            body: JSON.stringify({ employee_id, password }),
            // Needed so the browser stores the httpOnly `access_token` cookie when API_URL is cross-origin.
            credentials: "include",
        });

        const data = await readJsonSafely(res);

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
            let destination = "projects.html";
            if (data.role === "SUPER_ADMIN" || data.role === "ADMIN") {
                destination = "admin.html";
            } else if (data.role === "ADMIN_GLOSSAIRE") {
                destination = "glossary.html";
            }
            window.location.href = destination;
        }, 1000);

    } catch (err) {
        status.innerText = "Erreur de connexion au serveur.";
        status.className = "error";
        console.error(err);
    }
});

// Exécuter au chargement
checkAdminExists();
