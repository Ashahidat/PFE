const API_URL = "http://localhost:8000";
const token = localStorage.getItem("access_token");
const role = localStorage.getItem("user_role");
const glossaryAccessRoles = ["SUPER_ADMIN", "ADMIN", "ADMIN_GLOSSAIRE"];
if (!glossaryAccessRoles.includes(role)) {
    window.location.href = "projects.html";
}

if (!token) {
    window.location.href = "index.html";
}

let currentEditId = null;
const categoryCache = {};
const glossariesById = {};

function escapeHtml(str) {
    if (!str) return "";
    return str.replace(/[&<>]/g, (m) => {
        if (m === "&") return "&amp;";
        if (m === "<") return "&lt;";
        if (m === ">") return "&gt;";
        return m;
    });
}

async function ensureCategories(glossaryId) {
    if (!glossaryId) return [];
    const key = String(glossaryId);
    if (categoryCache[key]) {
        return categoryCache[key];
    }
    try {
        const res = await fetch(`${API_URL}/glossary/categories?glossary_id=${glossaryId}`, {
            headers: { Authorization: `Bearer ${token}` },
        });
        if (!res.ok) {
            categoryCache[glossaryId] = [];
            return [];
        }
        const data = await res.json();
        categoryCache[key] = data;
        return data;
    } catch (err) {
        console.error("Erreur chargement catégories:", err);
        categoryCache[key] = [];
        return [];
    }
}

function formatCategoryOptions(glossaryId, selectedId, includePlaceholder = true) {
    const key = String(glossaryId);
    const categories = categoryCache[key] || [];
    if (!categories.length) {
        return "<option value=''>Aucune catégorie disponible</option>";
    }
    const placeholder = includePlaceholder ? "<option value=''>Sélectionnez une catégorie</option>" : "";
    return (
        placeholder +
        categories
            .map(
                (cat) =>
                    `<option value="${cat.id}" ${selectedId && String(cat.id) === String(selectedId) ? "selected" : ""}>${escapeHtml(
                        cat.name
                    )}</option>`
            )
            .join("")
    );
}

async function refreshCategorySelect(glossaryId) {
    const select = document.getElementById("categorySelect");
    const help = document.getElementById("categoryHelp");
    if (!select) return;
    const categories = await ensureCategories(glossaryId);
    select.innerHTML = formatCategoryOptions(glossaryId, null);
    select.disabled = categories.length === 0;
    if (help) {
        help.textContent = categories.length
            ? `Catégories prêtes (${categories.length}) pour ce glossaire.`
            : "Aucune catégorie disponible pour ce glossaire.";
    }
}

async function refreshCategoryList(glossaryId) {
    const container = document.getElementById("categoryList");
    if (!container) return;
    if (!glossaryId) {
        container.innerHTML = "<p>Sélectionnez un glossaire pour voir ses catégories.</p>";
        return;
    }
    const categories = await ensureCategories(glossaryId);
    const glossaryName = glossariesById[String(glossaryId)]?.name || "Glossaire";
    if (!categories.length) {
        container.innerHTML = `<p>Aucune catégorie définie pour ${escapeHtml(glossaryName)}.</p>`;
        return;
    }
    container.innerHTML = `
        <strong>Catégories pour ${escapeHtml(glossaryName)} :</strong>
        <ul style="padding-left:20px; margin-top:8px;">
            ${categories
                .map(
                    (category) => `
                        <li>
                            <strong>${escapeHtml(category.name)}</strong>
                            <p style="margin:4px 0 0; font-size:12px;">
                                ${escapeHtml(category.description || "Pas de description")}
                            </p>
                            <div style="margin-top:6px;">
                                <button class="btn-edit" onclick="openCategoryEdit(${category.id})">✏️ Renommer</button>
                            </div>
                            <div class="edit-form" id="edit-category-form-${category.id}">
                                <h4>Modifier la catégorie</h4>
                                <input type="text" id="edit-category-name-${category.id}" value="${escapeHtml(category.name)}" placeholder="Nom *">
                                <textarea id="edit-category-desc-${category.id}" placeholder="Description">${escapeHtml(category.description || "")}</textarea>
                                <button onclick="saveCategoryEdit(${category.id}, ${category.glossary_id})" class="btn-save" style="margin-right:5px;">💾 Enregistrer</button>
                                <button onclick="closeCategoryEdit(${category.id})" style="background:#6c757d; color:white; border:none; padding:5px 10px; border-radius:3px;">Annuler</button>
                            </div>
                        </li>
                    `
                )
                .join("")}
        </ul>
    `;
}

window.openCategoryEdit = function (categoryId) {
    const form = document.getElementById(`edit-category-form-${categoryId}`);
    if (form) form.classList.add("active");
};

window.closeCategoryEdit = function (categoryId) {
    const form = document.getElementById(`edit-category-form-${categoryId}`);
    if (form) form.classList.remove("active");
};

window.saveCategoryEdit = async function (categoryId, glossaryId) {
    const name = (document.getElementById(`edit-category-name-${categoryId}`)?.value || "").trim();
    const description = (document.getElementById(`edit-category-desc-${categoryId}`)?.value || "").trim();

    if (!name) {
        alert("Le nom de la catégorie est obligatoire");
        return;
    }

    try {
        const res = await fetch(`${API_URL}/glossary/categories/${categoryId}`, {
            method: "PUT",
            headers: {
                "Content-Type": "application/json",
                Authorization: `Bearer ${token}`,
            },
            body: JSON.stringify({
                name,
                description: description || null,
            }),
        });

        if (!res.ok) {
            let detail = "Erreur";
            try {
                const err = await res.json();
                detail = err.detail || err.message || err.error || detail;
            } catch {
                try {
                    detail = await res.text();
                } catch {
                    detail = "Erreur";
                }
            }
            throw new Error(detail);
        }

        alert("✅ Catégorie modifiée");
        closeCategoryEdit(categoryId);
        delete categoryCache[String(glossaryId)];
        await refreshCategoryList(glossaryId);
        const selectedGlossaryId = document.getElementById("glossarySelect")?.value;
        if (selectedGlossaryId && String(selectedGlossaryId) === String(glossaryId)) {
            await refreshCategorySelect(glossaryId);
        }
        await loadTerms();
    } catch (err) {
        alert("❌ " + (err?.message || "Erreur de connexion"));
    }
};

function sortGlossaries(glossaries) {
    return glossaries.sort((a, b) => a.name.localeCompare(b.name));
}

function getGlossaryOptions(glossaries) {
    if (!glossaries?.length) {
        return "<option value=''>Créer un glossaire</option>";
    }
    return glossaries
        .map((g) => `<option value="${g.id}">${escapeHtml(g.name)}</option>`)
        .join("");
}

async function loadGlossaries() {
    try {
        const res = await fetch(`${API_URL}/glossary/glossaries`, {
            headers: { Authorization: `Bearer ${token}` },
        });
        if (!res.ok) throw new Error("Impossible de charger les glossaires");
        const glossaries = sortGlossaries(await res.json());
        const glossaryOptions = getGlossaryOptions(glossaries);
        const glossarySelect = document.getElementById("glossarySelect");
        const categoryGlossarySelect = document.getElementById("categoryGlossarySelect");
        if (glossarySelect) glossarySelect.innerHTML = glossaryOptions;
        if (categoryGlossarySelect) categoryGlossarySelect.innerHTML = glossaryOptions;
        glossaries.forEach((g) => {
            glossariesById[String(g.id)] = g;
        });
        const defaultId = glossaries[0]?.id || "";
        await refreshCategorySelect(defaultId);
        await refreshCategoryList(defaultId);
        renderGlossaryList(glossaries);
        document.getElementById("createBtn").disabled = glossaries.length === 0;
    } catch (err) {
        console.error("Erreur loadGlossaries:", err);
        document.getElementById("glossaryList").innerHTML =
            '<p style="color:red;">Impossible de récupérer les glossaires</p>';
    }
}

async function loadTerms() {
    try {
        const res = await fetch(`${API_URL}/glossary/terms`, {
            headers: { Authorization: `Bearer ${token}` },
        });
        if (!res.ok) {
            if (res.status === 401) {
                localStorage.clear();
                window.location.href = "index.html";
            }
            throw new Error("Erreur chargement");
        }
        const terms = await res.json();
        const glossaryIds = [...new Set(terms.map((t) => t.glossary_id))];
        await Promise.all(glossaryIds.map((id) => ensureCategories(id)));
        const container = document.getElementById("termsList");
        container.innerHTML = "";
        if (!terms.length) {
            container.innerHTML = "<p>Aucun terme dans les glossaires</p>";
            return;
        }
        terms.forEach((t) => {
            const div = document.createElement("div");
            div.className = "term-item";
            div.innerHTML = `
                <div class="term-info">
                    <strong>${escapeHtml(t.term)}</strong>
                    ${t.category_name ? `<span style="background: #e9ecef; padding: 2px 8px; border-radius: 12px; font-size: 12px; margin-left: 10px;">${escapeHtml(t.category_name)}</span>` : ''}
                    <p style="margin: 5px 0 0; color: #555;">${escapeHtml(t.description || "Aucune description")}</p>
                    <small>Créé par: ${t.created_by || "inconnu"} | ${t.created_at ? new Date(t.created_at).toLocaleDateString() : ""}</small>
                </div>
                <div>
                    <button class="btn-edit" onclick="openEditForm(${t.id}, '${escapeHtml(
                        t.term
                    )}', '${escapeHtml(t.description || "")}', '${escapeHtml(t.category_name || "")}', ${t.glossary_id})">✏️ Modifier</button>
                    <button class="btn-delete" onclick="deleteTerm(${t.id})">🗑️ Supprimer</button>
                </div>
            `;
            const editDiv = document.createElement("div");
            editDiv.className = "edit-form";
            editDiv.id = `edit-form-${t.id}`;
            editDiv.innerHTML = `
                <h4>Modifier le terme</h4>
                <select id="edit-glossary-${t.id}">
                    ${document.getElementById("glossarySelect").innerHTML}
                </select>
                <input type="text" id="edit-term-${t.id}" value="${escapeHtml(t.term)}" placeholder="Terme">
                <textarea id="edit-desc-${t.id}" placeholder="Description">${escapeHtml(t.description || "")}</textarea>
                <select id="edit-category-${t.id}">
                    ${formatCategoryOptions(t.glossary_id, t.category_id)}
                </select>
                <button onclick="saveEdit(${t.id})" class="btn-save" style="margin-right: 5px;">💾 Enregistrer</button>
                <button onclick="closeEditForm(${t.id})" style="background: #6c757d; color: white; border: none; padding: 5px 10px; border-radius: 3px;">Annuler</button>
            `;
            div.appendChild(editDiv);
            document.getElementById("termsList").appendChild(div);
        });
    } catch (err) {
        console.error("Erreur loadTerms:", err);
        document.getElementById("termsList").innerHTML = '<p style="color: red;">Erreur de chargement</p>';
    }
}

function renderGlossaryList(glossaries) {
    const container = document.getElementById("glossaryList");
    if (!glossaries.length) {
        container.innerHTML = "<p>Aucun glossaire défini</p>";
        return;
    }
    container.innerHTML = `
        <strong>Glossaires disponibles :</strong>
        <ul style="padding-left:20px;">
            ${glossaries
                .map(
                    (g) => `
                        <li>
                            <strong>${escapeHtml(g.name)}</strong>
                            ${g.department ? `(<em>${escapeHtml(g.department)}</em>)` : ""}
                            <br><small>${escapeHtml(g.description || "Pas de description")}</small>
                            <div style="margin-top:6px;">
                                <button class="btn-edit" onclick="openGlossaryEdit(${g.id})">✏️ Renommer</button>
                            </div>
                            <div class="edit-form" id="edit-glossary-form-${g.id}">
                                <h4>Modifier le glossaire</h4>
                                <input type="text" id="edit-glossary-name-${g.id}" value="${escapeHtml(g.name)}" placeholder="Nom affiché *">
                                <input type="text" id="edit-glossary-dept-${g.id}" value="${escapeHtml(g.department || "")}" placeholder="Département (optionnel)">
                                <textarea id="edit-glossary-desc-${g.id}" placeholder="Description">${escapeHtml(g.description || "")}</textarea>
                                <button onclick="saveGlossaryEdit(${g.id})" class="btn-save" style="margin-right:5px;">💾 Enregistrer</button>
                                <button onclick="closeGlossaryEdit(${g.id})" style="background:#6c757d; color:white; border:none; padding:5px 10px; border-radius:3px;">Annuler</button>
                            </div>
                        </li>
                    `
                )
                .join("")}
        </ul>
    `;
}

window.openGlossaryEdit = function (id) {
    const form = document.getElementById(`edit-glossary-form-${id}`);
    if (form) form.classList.add("active");
};

window.closeGlossaryEdit = function (id) {
    const form = document.getElementById(`edit-glossary-form-${id}`);
    if (form) form.classList.remove("active");
};

window.saveGlossaryEdit = async function (id) {
    const name = (document.getElementById(`edit-glossary-name-${id}`)?.value || "").trim();
    const department = (document.getElementById(`edit-glossary-dept-${id}`)?.value || "").trim();
    const description = (document.getElementById(`edit-glossary-desc-${id}`)?.value || "").trim();

    if (!name) {
        alert("Le nom du glossaire est obligatoire");
        return;
    }

    try {
        const res = await fetch(`${API_URL}/glossary/glossaries/${id}`, {
            method: "PUT",
            headers: {
                "Content-Type": "application/json",
                Authorization: `Bearer ${token}`,
            },
            body: JSON.stringify({
                name,
                department: department || null,
                description: description || null,
            }),
        });

        if (!res.ok) {
            let detail = "Erreur";
            try {
                const err = await res.json();
                detail = err.detail || err.message || err.error || detail;
            } catch {
                try {
                    detail = await res.text();
                } catch {
                    detail = "Erreur";
                }
            }
            throw new Error(detail);
        }

        alert("✅ Glossaire modifié");
        closeGlossaryEdit(id);
        await loadGlossaries();
        await loadTerms();
    } catch (err) {
        alert("❌ " + (err?.message || "Erreur de connexion"));
    }
};

function openEditForm(id, term, description, category, glossaryId) {
    currentEditId = id;
    const editForm = document.getElementById(`edit-form-${id}`);
    if (editForm) editForm.classList.add("active");
    const select = document.getElementById(`edit-glossary-${id}`);
    if (select) select.value = glossaryId;
}

function closeEditForm(id) {
    const editForm = document.getElementById(`edit-form-${id}`);
    if (editForm) editForm.classList.remove("active");
    currentEditId = null;
}

async function saveEdit(id) {
    const newTerm = document.getElementById(`edit-term-${id}`).value;
    const newDesc = document.getElementById(`edit-desc-${id}`).value;
    const newCat = document.getElementById(`edit-category-${id}`).value;
    const glossaryId = document.getElementById(`edit-glossary-${id}`).value;

    if (!newTerm) {
        alert("Le terme est obligatoire");
        return;
    }
    if (!newCat) {
        alert("La catégorie est obligatoire");
        return;
    }

    try {
        const res = await fetch(`${API_URL}/glossary/terms/${id}`, {
            method: "PUT",
            headers: {
                "Content-Type": "application/json",
                Authorization: `Bearer ${token}`,
            },
            body: JSON.stringify({
                glossary_id: glossaryId,
                term: newTerm,
                description: newDesc || null,
                category_id: newCat,
            }),
        });
        if (res.ok) {
            alert("✅ Terme modifié");
            closeEditForm(id);
            loadTerms();
        } else {
            let detail = "Erreur inconnue";
            try {
                const err = await res.json();
                detail = err.detail || err.message || err.error || detail;
            } catch (parseErr) {
                try {
                    detail = await res.text();
                } catch {
                    detail = "Erreur inconnue";
                }
            }
            alert("❌ Erreur: " + detail);
        }
    } catch (err) {
        alert("❌ Erreur de connexion");
    }
}

window.deleteTerm = async function (id) {
    if (!confirm("Supprimer ce terme ?")) return;
    try {
        const res = await fetch(`${API_URL}/glossary/terms/${id}`, {
            method: "DELETE",
            headers: { Authorization: `Bearer ${token}` },
        });
        if (res.ok) {
            alert("✅ Terme supprimé");
            loadTerms();
        }
    } catch (err) {
        alert("❌ Erreur de connexion");
    }
};

document.getElementById("createBtn").addEventListener("click", async () => {
    const termInput = document.getElementById("term").value;
    const description = document.getElementById("description").value;
    const categoryId = document.getElementById("categorySelect").value;
    const statusDiv = document.getElementById("createStatus");
    const glossaryId = document.getElementById("glossarySelect").value;

    if (!termInput) {
        statusDiv.innerText = "Le terme est obligatoire";
        statusDiv.style.color = "red";
        return;
    }
    if (!glossaryId) {
        statusDiv.innerText = "Ajoute d'abord un glossaire";
        statusDiv.style.color = "red";
        return;
    }
    if (!categoryId) {
        statusDiv.innerText = "Sélectionne une catégorie";
        statusDiv.style.color = "red";
        return;
    }

    try {
        const res = await fetch(`${API_URL}/glossary/terms`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                Authorization: `Bearer ${token}`,
            },
            body: JSON.stringify({
                glossary_id: glossaryId,
                category_id: categoryId,
                term: termInput,
                description: description || null,
            }),
        });
        if (res.ok) {
            statusDiv.innerText = "✅ Terme ajouté";
            statusDiv.style.color = "green";
            document.getElementById("term").value = "";
            document.getElementById("description").value = "";
            document.getElementById("categorySelect").value = "";
            loadTerms();
            setTimeout(() => {
                statusDiv.innerText = "";
            }, 3000);
        } else {
            let detail = "Erreur";
            try {
                const err = await res.json();
                detail = err.detail || err.message || err.error || "Erreur";
            } catch (parseErr) {
                try {
                    detail = await res.text();
                } catch {
                    detail = "Erreur";
                }
            }
            statusDiv.innerText = "❌ " + detail;
            statusDiv.style.color = "red";
        }
    } catch (err) {
        console.error("Erreur lors de la création du terme :", err);
        const message = err?.message || "Erreur de connexion";
        statusDiv.innerText = `❌ ${message}`;
        statusDiv.style.color = "red";
    }
});

document.getElementById("createCategoryBtn").addEventListener("click", async () => {
    const name = document.getElementById("category-name").value;
    const description = document.getElementById("category-description").value;
    const glossaryId = document.getElementById("categoryGlossarySelect").value;
    const status = document.getElementById("createCategoryStatus");

    if (!glossaryId) {
        status.innerText = "Ajoute d'abord un glossaire";
        status.style.color = "red";
        return;
    }
    if (!name) {
        status.innerText = "Le nom de la catégorie est obligatoire";
        status.style.color = "red";
        return;
    }

    try {
        const res = await fetch(`${API_URL}/glossary/categories`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                Authorization: `Bearer ${token}`,
            },
            body: JSON.stringify({
                glossary_id: glossaryId,
                name,
                description: description || null,
            }),
        });
        if (res.ok) {
            status.innerText = "✅ Catégorie créée";
            status.style.color = "green";
            document.getElementById("category-name").value = "";
            document.getElementById("category-description").value = "";
            delete categoryCache[String(glossaryId)];
            await refreshCategoryList(glossaryId);
            const selectedGlossaryId = document.getElementById("glossarySelect").value;
            if (selectedGlossaryId === glossaryId) {
                await refreshCategorySelect(glossaryId);
            }
            setTimeout(() => {
                status.innerText = "";
            }, 3000);
        } else {
            let detail = "Erreur";
            try {
                const err = await res.json();
                detail = err.detail || err.message || err.error || detail;
            } catch {
                try {
                    detail = await res.text();
                } catch {
                    detail = "Erreur";
                }
            }
            status.innerText = "❌ " + detail;
            status.style.color = "red";
        }
    } catch (err) {
        status.innerText = "❌ Erreur de connexion";
        status.style.color = "red";
    }
});

document.getElementById("createGlossaryBtn").addEventListener("click", async () => {
    const name = document.getElementById("glossary-name").value;
    const department = document.getElementById("glossary-dept").value;
    const description = document.getElementById("glossary-description").value;
    const status = document.getElementById("createGlossaryStatus");

    if (!name) {
        status.innerText = "Le nom du glossaire est obligatoire";
        status.style.color = "red";
        return;
    }

    try {
        const res = await fetch(`${API_URL}/glossary/glossaries`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                Authorization: `Bearer ${token}`,
            },
            body: JSON.stringify({
                name,
                qualified_name: name.toLowerCase().replace(/[^a-z0-9]+/g, "_"),
                description: description || null,
                department: department || null,
            }),
        });
        if (res.ok) {
            status.innerText = "✅ Glossaire créé";
            status.style.color = "green";
            document.getElementById("glossary-name").value = "";
            document.getElementById("glossary-dept").value = "";
            document.getElementById("glossary-description").value = "";
            loadGlossaries();
            setTimeout(() => {
                status.innerText = "";
            }, 3000);
        } else {
            const err = await res.json();
            status.innerText = "❌ " + (err.detail || "Erreur");
            status.style.color = "red";
        }
    } catch (err) {
        status.innerText = "❌ Erreur de connexion";
        status.style.color = "red";
    }
});

const glossarySelectElement = document.getElementById("glossarySelect");
const categoryGlossarySelectElement = document.getElementById("categoryGlossarySelect");
if (glossarySelectElement) {
    glossarySelectElement.addEventListener("change", (event) => {
        refreshCategorySelect(event.target.value);
    });
}
if (categoryGlossarySelectElement) {
    categoryGlossarySelectElement.addEventListener("change", (event) => {
        refreshCategoryList(event.target.value);
    });
}

loadGlossaries();
loadTerms();
