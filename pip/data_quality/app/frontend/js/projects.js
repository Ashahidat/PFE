const API_URL = "http://localhost:8000";

document.addEventListener("DOMContentLoaded", () => {
    loadProjects();
    
    document.getElementById("createProjectBtn").addEventListener("click", createProject);
});

async function loadProjects() {
    const token = localStorage.getItem("access_token");
    
    if (!token) {
        window.location.href = "index.html";
        return;
    }
    
    try {
        const res = await fetch(`${API_URL}/projects/`, {
            headers: {
                "Authorization": `Bearer ${token}`
            }
        });
        
        const projects = await res.json();
        displayProjects(projects);
    } catch (err) {
        console.error("Erreur chargement projets:", err);
        document.getElementById("projectsList").innerHTML = 
            '<p class="error">Erreur de chargement</p>';
    }
}

async function createProject() {
    const name = document.getElementById("projectName").value;
    const description = document.getElementById("projectDesc").value;
    // ✅ Récupérer la visibilité choisie
    const visibility = document.querySelector('input[name="visibility"]:checked').value;
    const token = localStorage.getItem("access_token");
    
    if (!name) {
        alert("Le nom du projet est requis");
        return;
    }
    
    try {
        const res = await fetch(`${API_URL}/projects/`, {
            method: "POST",
            headers: {
                "Authorization": `Bearer ${token}`,
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ 
                name, 
                description,
                visibility  // ✅ AJOUTÉ
            })
        });
        
        if (res.ok) {
            document.getElementById("projectName").value = "";
            document.getElementById("projectDesc").value = "";
            loadProjects(); // Recharger la liste
        } else {
            const error = await res.json();
            alert("Erreur création projet: " + (error.detail || "Erreur inconnue"));
        }
    } catch (err) {
        console.error("Erreur:", err);
        alert("Erreur de connexion au serveur");
    }
}

function displayProjects(projects) {
    const container = document.getElementById("projectsList");
    
    if (projects.length === 0) {
        container.innerHTML = '<p>Aucun projet pour le moment</p>';
        return;
    }
    
    let html = '';
    projects.forEach(p => {
        // ✅ Afficher un badge de visibilité
        const visibilityBadge = p.visibility === 'PUBLIC' 
            ? '<span class="badge public">🌍 PUBLIC</span>' 
            : '<span class="badge department">🏢 Département</span>';
        
        html += `
            <div class="project-item">
                <div class="project-info">
                    <h3>${p.name} ${visibilityBadge}</h3>
                    <p>${p.description || 'Aucune description'}</p>
                    <div class="project-meta">
                        <small>Créé par: ${p.owner_employee_id}</small>
                        <small>📊 ${p.datasets_count} datasets</small>
                    </div>
                </div>
                <div>
                    <button onclick="selectProject('${p.id}', '${p.name}')" class="select-project">
                        Utiliser ce projet
                    </button>
                </div>
            </div>
        `;
    });
    
    container.innerHTML = html;
}

// ✅ Modifié pour accepter le nom aussi
function selectProject(projectId, projectName) {
    localStorage.setItem("current_project_id", projectId);
    localStorage.setItem("current_project_name", projectName);
    window.location.href = "upload.html";
}

// Déconnexion
document.getElementById("logoutBtn")?.addEventListener("click", () => {
    localStorage.clear();
    window.location.href = "index.html";
});