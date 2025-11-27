/**
 * Affiche un message de chargement animé et gère le timeout.
 * @param {HTMLElement} container - L'élément où afficher le message.
 * @param {Function} asyncFunc - Fonction async qui retourne une promesse (fetch, traitement, etc.)
 * @param {number} timeout - Temps max avant message "Chargement long" (ms), défaut 10000
 */
async function withLoading(container, asyncFunc, timeout = 300) {
    let dots = '';
    container.innerText = 'Chargement';

    // Animation des points
    const interval = setInterval(() => {
        dots = dots.length < 3 ? dots + '.' : '';
        container.innerText = 'Chargement' + dots;
    }, 500);

    // Timer pour message "chargement long"
    const longTimer = setTimeout(() => {
        container.innerText = 'Le chargement prend plus de temps que prévu…';
    }, timeout);

    try {
        const result = await asyncFunc();
        clearInterval(interval);
        clearTimeout(longTimer);
        container.innerText = '✅ Terminé !';
        return result;
    } catch (err) {
        clearInterval(interval);
        clearTimeout(longTimer);
        container.innerText = '❌ Erreur lors du chargement.';
        throw err;
    }
}
