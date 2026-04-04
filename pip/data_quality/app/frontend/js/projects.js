const API_URL = "http://localhost:8000";
const token = localStorage.getItem("access_token");

if (!token) window.location.href = "index.html";

async function loadProjects() {
    try {
        const res = await fetch(`${API_URL}/projects/`, {
            headers: { "Authorization": `Bearer ${token}` }
        });
        const projects = await res.json();
        displayProjects(projects);
    } catch (err) {
        console.error(err);
        document.getElementById("projectsList").innerHTML = '<p style="color: red;">Erreur de chargement</p>';
    }
}

function displayProjects(projects) {
    const container = document.getElementById("projectsList");
    if (projects.length === 0) {
        container.innerHTML = '<p>Aucun projet</p>';
        return;
    }
    let html = '';
    projects.forEach(p => {
        const badge = p.visibility === 'PUBLIC' 
            ? '<span style="background: #28a745; padding: 2px 8px; border-radius: 12px; font-size: 12px; color: white;">PUBLIC</span>'
            : '<span style="background: #ffc107; padding: 2px 8px; border-radius: 12px; font-size: 12px;">DÉPARTEMENT</span>';
        html += `
            <div style="border: 1px solid #ddd; padding: 10px; margin: 5px 0; border-radius: 5px; display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <strong>${p.name}</strong> ${badge}
                    <p style="margin: 5px 0;">${p.description || ''}</p>
                    <small>Créé par: ${p.owner_employee_id}</small>
                </div>
                <button onclick="selectProject('${p.id}', '${p.name}')" style="background: #007bff; color: white; border: none; padding: 5px 10px; border-radius: 3px;">Utiliser</button>
            </div>
        `;
    });
    container.innerHTML = html;
}

window.selectProject = function(projectId, projectName) {
    localStorage.setItem("current_project_id", projectId);
    localStorage.setItem("current_project_name", projectName);
    window.location.href = "upload.html";
};

document.getElementById("createProjectBtn").addEventListener("click", async () => {
    const name = document.getElementById("projectName").value;
    const description = document.getElementById("projectDesc").value;
    const visibility = document.querySelector('input[name="visibility"]:checked').value;
    
    if (!name) {
        alert("Nom requis");
        return;
    }
    
    try {
        const res = await fetch(`${API_URL}/projects/`, {
            method: "POST",
            headers: {
                "Authorization": `Bearer ${token}`,
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ name, description, visibility })
        });
        
        if (res.ok) {
            document.getElementById("projectName").value = "";
            document.getElementById("projectDesc").value = "";
            loadProjects();
        } else {
            const error = await res.json();
            alert("Erreur: " + (error.detail || "Erreur"));
        }
    } catch (err) {
        alert("Erreur de connexion");
    }
});

loadProjects();