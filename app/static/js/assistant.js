let fichierSelectionne = null;

function toggleAssistant() {
    const drawer = document.getElementById('assistantDrawer');
    drawer.classList.toggle('open');
}

function scrollToBottom() {
    const zone = document.getElementById('chatMessages');
    zone.scrollTop = zone.scrollHeight;
}

function afficherMessage(texte, role) {
    const div = document.createElement('div');
    div.className = `message ${role}`;
    div.textContent = texte;
    document.getElementById('chatMessages').appendChild(div);
    scrollToBottom();
}

function afficherTyping() {
    const div = document.createElement('div');
    div.id = 'typingIndicator';
    div.className = 'message ia typing';
    div.innerHTML = '<span></span><span></span><span></span>';
    document.getElementById('chatMessages').appendChild(div);
    scrollToBottom();
}

function retirerTyping() {
    document.getElementById('typingIndicator')?.remove();
}

/* Gestion de la sélection du PDF */
function gererFichier(input) {
    if (input.files && input.files[0]) {
        fichierSelectionne = input.files[0];
        document.getElementById('fileName').textContent = fichierSelectionne.name;
        document.getElementById('filePreview').style.display = 'flex';
    }
}

function annulerFichier() {
    fichierSelectionne = null;
    document.getElementById('fileInput').value = '';
    document.getElementById('filePreview').style.display = 'none';
}

/* Gestion du champ de saisie */
const textarea = document.getElementById('userInput');

textarea.addEventListener('input', () => {
    textarea.style.height = 'auto';
    textarea.style.height = textarea.scrollHeight + 'px';
});

textarea.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

/* Envoi dynamique (Fichier et/ou Question) */
async function sendMessage() {
    const question = textarea.value.trim();
    if (!question && !fichierSelectionne) return;

    // 1. Traitement du fichier PDF s'il y en a un
    if (fichierSelectionne) {
        afficherMessage(`📁 Document joint : ${fichierSelectionne.name}`, 'user');
        afficherTyping();

        const formData = new FormData();
        formData.append('fichier', fichierSelectionne);
        formData.append('titre', fichierSelectionne.name);

        try {
            const resFile = await fetch('/ressource/ajouter/', {
                method: 'POST',
                body: formData
            });
            const dataFile = await resFile.json();
            retirerTyping();

            if (dataFile.status === 'success') {
                afficherMessage(`✅ Document indexé ${dataFile.ia}`, 'ia');
            } else {
                afficherMessage(`⚠️ Erreur d'indexation : ${dataFile.erreur || 'Échec du traitement'}`, 'ia');
            }
        } catch (e) {
            retirerTyping();
            afficherMessage("⚠️ Erreur réseau lors de l'envoi du fichier.", 'ia');
        }

        annulerFichier();
    }

    // 2. Traitement de la question texte
    if (question) {
        afficherMessage(question, 'user');
        textarea.value = '';
        textarea.style.height = 'auto';

        afficherTyping();

        try {
            const response = await fetch('/assistant_ia/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ question: question })
            });

            const data = await response.json();
            retirerTyping();

            if (data.reponse) {
                afficherMessage(data.reponse, 'ia');
            } else {
                afficherMessage("Désolé, une erreur est survenue.", 'ia');
            }
        } catch (error) {
            retirerTyping();
            afficherMessage("Erreur de connexion avec le serveur.", 'ia');
        }
    }
}
