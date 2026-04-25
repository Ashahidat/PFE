const puter = require('@heyputer/puter.js');

async function testCodex() {
    try {
        console.log("Génération de code en cours...");
        const puterjs = puter.default || puter;
        console.log("Objet puterjs:", Object.keys(puterjs));
        
        // Essayer différentes façons d'appeler l'API
        if (puterjs.ai && puterjs.ai.chat) {
            const response = await puterjs.ai.chat(
                "Écris une fonction Python pour uploader un fichier sur un serveur S3.",
                { model: 'openai/gpt-5.3-codex' }
            );
            console.log("--- Réponse de Codex ---");
            console.log(response);
        } else if (puterjs.chat) {
            const response = await puterjs.chat(
                "Écris une fonction Python pour uploader un fichier sur un serveur S3.",
                { model: 'openai/gpt-5.3-codex' }
            );
            console.log("--- Réponse de Codex ---");
            console.log(response);
        } else {
            console.log("Structure de l'objet :");
            console.log(puterjs);
        }
    } catch (error) {
        console.error("Erreur :", error.message);
        console.error("Détails :", error);
    }
}

testCodex();
