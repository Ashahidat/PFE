const API_URL = "http://localhost:8000";
const token = localStorage.getItem("access_token");
const role = localStorage.getItem("user_role");

// Vérifier authentification (seul ADMIN peut accéder à cette page)
if (!token) {
    window.location.href = "index.html";
}

let currentEditId = null;

async function loadTerms() {
    try {
        const res = await fetch(`${API_URL}/glossary/terms`, {
            headers: { "Authorization": `Bearer ${token}` }
        });
        
        if (!res.ok) {
            if (res.status === 401) {
                localStorage.clear();
                window.location.href = "index.html";
            }
            throw new Error("Erreur chargement");
        }
        
        const terms = await res.json();
        const container = document.getElementById("termsList");
        container.innerHTML = "";
        
        if (terms.length === 0) {
            container.innerHTML = '<p>Aucun terme dans le glossaire</p>';
            return;
        }
        
        for (const t of terms) {
            const div = document.createElement("div");
            div.className = "term-item";
            div.id = `term-${t.id}`;
            
            div.innerHTML = `
                <div class="term-info">
                    <strong>${escapeHtml(t.term)}</strong>
                    ${t.category ? `<span style="background: #e9ecef; padding: 2px 8px; border-radius: 12px; font-size: 12px; margin-left: 10px;">${escapeHtml(t.category)}</span>` : ''}
                    <p style="margin: 5px 0 0; color: #555;">${escapeHtml(t.description || 'Aucune description')}</p>
                    <small>Créé par: ${t.created_by || 'inconnu'} | ${t.created_at ? new Date(t.created_at).toLocaleDateString() : ''}</small>
                </div>
                <div>
                    <button class="btn-edit" onclick="openEditForm(${t.id}, '${escapeHtml(t.term)}', '${escapeHtml(t.description || '')}', '${escapeHtml(t.category || '')}')">✏️ Modifier</button>
                    <button class="btn-delete" onclick="deleteTerm(${t.id})">🗑️ Supprimer</button>
                </div>
            `;
            
            // Ajouter formulaire d'édition (caché)
            const editDiv = document.createElement("div");
            editDiv.className = "edit-form";
            editDiv.id = `edit-form-${t.id}`;
            editDiv.innerHTML = `
                <h4>Modifier le terme</h4>
                <input type="text" id="edit-term-${t.id}" value="${escapeHtml(t.term)}" placeholder="Terme">
                <textarea id="edit-desc-${t.id}" placeholder="Description">${escapeHtml(t.description || '')}</textarea>
                <input type="text" id="edit-cat-${t.id}" value="${escapeHtml(t.category || '')}" placeholder="Catégorie">
                <button onclick="saveEdit(${t.id})" class="btn-save" style="margin-right: 5px;">💾 Enregistrer</button>
                <button onclick="closeEditForm(${t.id})" style="background: #6c757d; color: white; border: none; padding: 5px 10px; border-radius: 3px;">Annuler</button>
            `;
            div.appendChild(editDiv);
            container.appendChild(div);
        }
    } catch (err) {
        console.error("Erreur loadTerms:", err);
        document.getElementById("termsList").innerHTML = '<p style="color: red;">Erreur de chargement</p>';
    }
}

function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/[&<>]/g, function(m) {
        if (m === '&') return '&amp;';
        if (m === '<') return '&lt;';
        if (m === '>') return '&gt;';
        return m;
    });
}

window.openEditForm = function(id, term, description, category) {
    currentEditId = id;
    const editForm = document.getElementById(`edit-form-${id}`);
    if (editForm) {
        editForm.classList.add("active");
    }
};

window.closeEditForm = function(id) {
    const editForm = document.getElementById(`edit-form-${id}`);
    if (editForm) {
        editForm.classList.remove("active");
    }
    currentEditId = null;
};

window.saveEdit = async function(id) {
    const newTerm = document.getElementById(`edit-term-${id}`).value;
    const newDesc = document.getElementById(`edit-desc-${id}`).value;
    const newCat = document.getElementById(`edit-cat-${id}`).value;
    
    if (!newTerm) {
        alert("Le terme est obligatoire");
        return;
    }
    
    try {
        const res = await fetch(`${API_URL}/glossary/terms/${id}`, {
            method: "PUT",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${token}`
            },
            body: JSON.stringify({
                term: newTerm,
                description: newDesc || null,
                category: newCat || null
            })
        });
        
        if (res.ok) {
            alert("✅ Terme modifié");
            closeEditForm(id);
            loadTerms();
        } else {
            const err = await res.json();
            alert("❌ Erreur: " + (err.detail || "Erreur inconnue"));
        }
    } catch (err) {
        alert("❌ Erreur de connexion");
    }
};

window.deleteTerm = async function(id) {
    if (!confirm("Supprimer ce terme ?")) return;
    
    try {
        const res = await fetch(`${API_URL}/glossary/terms/${id}`, {
            method: "DELETE",
            headers: { "Authorization": `Bearer ${token}` }
        });
        
        if (res.ok) {
            alert("✅ Terme supprimé");
            loadTerms();
        } else {
            const err = await res.json();
            alert("❌ Erreur: " + (err.detail || "Erreur inconnue"));
        }
    } catch (err) {
        alert("❌ Erreur de connexion");
    }
};

// Créer un terme
document.getElementById("createBtn").addEventListener("click", async () => {
    const term = document.getElementById("term").value;
    const description = document.getElementById("description").value;
    const category = document.getElementById("category").value;
    const statusDiv = document.getElementById("createStatus");
    
    if (!term) {
        statusDiv.innerText = "Le terme est obligatoire";
        statusDiv.style.color = "red";
        return;
    }
    
    try {
        const res = await fetch(`${API_URL}/glossary/terms`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${token}`
            },
            body: JSON.stringify({
                term: term,
                description: description || null,
                category: category || null
            })
        });
        
        if (res.ok) {
            statusDiv.innerText = "✅ Terme ajouté";
            statusDiv.style.color = "green";
            document.getElementById("term").value = "";
            document.getElementById("description").value = "";
            document.getElementById("category").value = "";
            loadTerms();
            setTimeout(() => { statusDiv.innerText = ""; }, 3000);
        } else {
            const err = await res.json();
            statusDiv.innerText = "❌ " + (err.detail || "Erreur");
            statusDiv.style.color = "red";
        }
    } catch (err) {
        statusDiv.innerText = "❌ Erreur de connexion";
        statusDiv.style.color = "red";
    }
});

// Chargement initial
loadTerms();