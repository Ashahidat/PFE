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
        console.log("🟡 Tentative de connexion...");
        console.log(`👤 Employee ID: ${employee_id}`);

        const res = await fetch(`${API_URL}/login`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ employee_id, password })
        });

        console.log(`📊 Réponse login: ${res.status} ${res.statusText}`);
        const data = await res.json();
        console.log("📨 Données reçues login:", data);

        if (!res.ok) {
            status.innerText = data.detail || "Identifiants incorrects.";
            status.className = "error";
            return;
        }

        // ✅ CORRECTION : Stocker le token dans le localStorage
        if (data.access_token) {
            localStorage.setItem("access_token", data.access_token);
            console.log("✅ Token stocké:", data.access_token.substring(0, 20) + "...");
        } else {
            console.error("❌ Pas de token dans la réponse");
        }

        status.innerText = "Connexion réussie !";
        status.className = "success";

        setTimeout(() => window.location.href = "upload.html", 1000);

    } catch (err) {
        status.innerText = "Erreur de connexion au serveur.";
        status.className = "error";
        console.error("💥 Erreur complète login:", err);
    }
});