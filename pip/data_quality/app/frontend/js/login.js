const API_URL = "http://localhost:8000";

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

        status.innerText = "Connexion réussie !";
        status.className = "success";

        // plus tard tu pourras stocker un token
        setTimeout(() => window.location.href = "upload.html", 1000);

    } catch (err) {
        status.innerText = "Erreur de connexion au serveur.";
        status.className = "error";
        console.error(err);
    }
});
