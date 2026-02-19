const API_URL = "http://localhost:8000";

document.addEventListener("DOMContentLoaded", () => {
    loadProjects();
    
    document.getElementById("createProjectBtn").addEventListener("click", createProject);
});

async function loadProjects() {
    const token = localStorage.getItem("access_token");
    
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
            body: JSON.stringify({ name, description })
        });
        
        if (res.ok) {
            document.getElementById("projectName").value = "";
            document.getElementById("projectDesc").value = "";
            loadProjects(); // Recharger la liste
        } else {
            alert("Erreur création projet");
        }
    } catch (err) {
        console.error("Erreur:", err);
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
        html += `
            <div class="project-item">
                <div class="project-info">
                    <h3>${p.name}</h3>
                    <p>${p.description || 'Aucune description'}</p>
                    <div class="project-stats">
                        📊 ${p.datasets_count} datasets
                    </div>
                </div>
                <div>
                    <button onclick="selectProject('${p.id}')" class="select-project">
                        Utiliser ce projet
                    </button>
                </div>
            </div>
        `;
    });
    
    container.innerHTML = html;
}

function selectProject(projectId) {
    localStorage.setItem("current_project_id", projectId);
    localStorage.setItem("current_project_name", 
        document.querySelector(`button[onclick="selectProject('${projectId}')"]`)
            .closest('.project-item').querySelector('h3').textContent
    );
    window.location.href = "upload.html";
}