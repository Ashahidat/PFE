// js/navbar.js
function loadNavbar() {
    const token = localStorage.getItem("access_token");
    const role = localStorage.getItem("user_role");
    
    if (!token) return;
    
    let navHtml = `
        <nav style="background: #2c3e50; color: white; padding: 12px 20px; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 2px 5px rgba(0,0,0,0.1);">
            <div style="display: flex; gap: 25px; align-items: center;">
                <a href="projects.html" style="color: white; text-decoration: none; font-weight: bold;">📁 Projets</a>
    `;
    
    if (role === "ADMIN") {
        navHtml += `<a href="admin.html" style="color: white; text-decoration: none;">👥 Gestion users</a>`;
        navHtml += `<a href="glossary.html" style="color: white; text-decoration: none;">📖 Glossaire</a>`;
    }
        
    navHtml += `
            </div>
            <div style="display: flex; gap: 20px; align-items: center;">
                <a href="profile.html" style="color: white; text-decoration: none;">👤 Mon profil</a>
                <button id="navLogoutBtn" style="background: #e74c3c; color: white; border: none; padding: 6px 15px; border-radius: 5px; cursor: pointer; font-size: 14px;">Déconnexion</button>
            </div>
        </nav>
    `;
    
    const navPlaceholder = document.getElementById("navbar-placeholder");
    if (navPlaceholder) {
        navPlaceholder.innerHTML = navHtml;
        
        document.getElementById("navLogoutBtn")?.addEventListener("click", () => {
            localStorage.clear();
            window.location.href = "index.html";
        });
    }
}

document.addEventListener("DOMContentLoaded", loadNavbar);
