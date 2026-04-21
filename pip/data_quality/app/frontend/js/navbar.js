// js/navbar.js
function loadNavbar() {
    const token = localStorage.getItem("access_token");
    const role = localStorage.getItem("user_role");
    const adminRoles = ["ADMIN", "ADMIN_GLOSSAIRE", "SUPER_ADMIN"];
    const canUpload = role && role !== "AUDIT";

    if (!token) return;

    const uploadLink = canUpload
        ? '<a href="my-uploads.html">Mes uploads</a>'
        : '';

    let navHtml = `
            <nav class="app-nav">
                <div class="app-nav__inner">
                <div class="app-nav__left">
                    <a class="app-nav__brand" href="projects.html">Projets</a>
                    ${uploadLink}
        `;

    if (adminRoles.includes(role)) {
        navHtml += `<a href="glossary.html">Glossaire</a>`;
        navHtml += `<a href="admin.html">Utilisateurs</a>`;
    }
        
    navHtml += `
            </div>
            <div class="app-nav__right">
                <a href="profile.html">Mon profil</a>
                <button id="navLogoutBtn" class="app-nav__logout">Déconnexion</button>
            </div>
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
