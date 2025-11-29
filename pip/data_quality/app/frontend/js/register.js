const API_URL = "http://localhost:8000";

document.getElementById("registerBtn").addEventListener("click", async () => {
    const employee_id = document.getElementById("employee_id").value;
    const username = document.getElementById("username").value;
    const password = document.getElementById("password").value;
    const department = document.getElementById("department").value;
    const business_unit = document.getElementById("business_unit").value;

    const status = document.getElementById("status");
    status.classList.remove("hidden");

    if (!employee_id || !username || !password) {
        status.innerText = "Veuillez remplir tous les champs obligatoires.";
        status.className = "error";
        return;
    }

    try {
        const res = await fetch(`${API_URL}/register`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                employee_id,
                username,
                password,
                department,
                business_unit
            })
        });

        const data = await res.json();

        if (!res.ok) {
            status.innerText = data.detail || "Erreur lors de l'inscription.";
            status.className = "error";
            return;
        }

        status.innerText = "Inscription réussie ! Redirection...";
        status.className = "success";

        setTimeout(() => window.location.href = "index.html", 1000);

    } catch (err) {
        status.innerText = "Erreur de connexion au serveur.";
        status.className = "error";
        console.error(err);
    }
});
