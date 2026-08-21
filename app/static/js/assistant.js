let conversationActive = null;
let fichierSelectionne = null;

document.addEventListener('DOMContentLoaded', () => {
    chargerListeConversations();
});

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

function toggleAssistant() {
    const drawer = document.getElementById('assistantDrawer');
    if (drawer) drawer.classList.toggle('closed');
}

function toggleSidebar() {
    const drawer = document.getElementById('assistantDrawer');
    if (drawer) drawer.classList.toggle('sidebar-closed');
}

function obtenirCategorieDate(dateStr) {
    if (!dateStr) return 'Plus ancien';
    const dateConv = new Date(dateStr);
    const maintenant = new Date();
    const aujourdhui = new Date(maintenant.getFullYear(), maintenant.getMonth(), maintenant.getDate());
    const hier = new Date(aujourdhui);
    hier.setDate(hier.getDate() - 1);
    const septJours = new Date(aujourdhui);
    septJours.setDate(septJours.getDate() - 7);

    if (dateConv >= aujourdhui) return "Aujourd'hui";
    if (dateConv >= hier) return 'Hier';
    if (dateConv >= septJours) return '7 derniers jours';
    return 'Plus ancien';
}

async function chargerListeConversations() {
    const historyList = document.getElementById('historyList');
    if (!historyList) return;

    try {
        const reponse = await fetch('/conversations/');
        const data = await reponse.json();
        const conversations = data.conversations || [];

        historyList.innerHTML = '';
        if (conversations.length === 0) {
            historyList.innerHTML = '<span class="history-empty">Aucune discussion</span>';
            return;
        }

        const groupes = {
            "Aujourd'hui": [],
            "Hier": [],
            "7 derniers jours": [],
            "Plus ancien": []
        };

        conversations.forEach(conv => {
            const cat = obtenirCategorieDate(conv.date_creation);
            groupes[cat].push(conv);
        });

        Object.keys(groupes).forEach(titreGroupe => {
            const liste = groupes[titreGroupe];
            if (liste.length > 0) {
                const sectionHeader = document.createElement('span');
                sectionHeader.className = 'section-title';
                sectionHeader.textContent = titreGroupe;
                historyList.appendChild(sectionHeader);

                liste.forEach(conv => {
                    const item = document.createElement('div');
                    item.className = `history-item ${conv.id === conversationActive ? 'active' : ''}`;

                    const span = document.createElement('span');
                    span.textContent = conv.titre || 'Nouvelle conversation';
                    span.className = 'history-item-titre';

                    item.appendChild(span);
                    item.onclick = () => chargerConversation(conv.id);

                    item.ondblclick = (e) => {
                        e.stopPropagation();
                        activerRenommage(item, span, conv.id, conv.titre);
                    };

                    historyList.appendChild(item);
                });
            }
        });
    } catch (err) {
        console.error('Erreur lors du chargement des conversations :', err);
    }
}

function activerRenommage(item, span, id, titreActuel) {
    const input = document.createElement('input');
    input.type = 'text';
    input.value = titreActuel || '';
    input.className = 'history-rename-input';

    item.replaceChild(input, span);
    input.focus();
    input.select();

    const valider = async () => {
        const nouveauTitre = input.value.trim();
        if (nouveauTitre && nouveauTitre !== titreActuel) {
            try {
                await fetch(`/conversations/${id}/renommer/`, {
                    method: 'POST',
                    headers: { 
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCookie('csrftoken')
                    },
                    body: JSON.stringify({ titre: nouveauTitre })
                });
            } catch (err) {
                console.error('Erreur lors du renommage :', err);
            }
        }
        chargerListeConversations();
    };

    input.addEventListener('blur', valider);
    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            input.blur();
        }
        if (e.key === 'Escape') {
            input.value = titreActuel;
            input.blur();
        }
    });
}

async function chargerConversation(id) {
    conversationActive = id;
    const chatMessages = document.getElementById('chatMessages');
    if (!chatMessages) return;

    chatMessages.innerHTML = '<div class="message ia">Chargement de la conversation...</div>';

    try {
        const reponse = await fetch(`/conversations/${id}/`);
        const data = await reponse.json();

        chatMessages.innerHTML = '';
        if (data.messages && data.messages.length > 0) {
            data.messages.forEach(msg => {
                const bubble = document.createElement('div');
                bubble.className = `message ${msg.role === 'user' ? 'user' : 'ia'}`;
                bubble.textContent = msg.contenu;
                chatMessages.appendChild(bubble);
            });
        } else {
            chatMessages.innerHTML = '<div class="message ia">Discussion vide. Posez une question !</div>';
        }
        chatMessages.scrollTop = chatMessages.scrollHeight;
        chargerListeConversations();
    } catch (err) {
        console.error('Erreur lors du chargement de la conversation :', err);
        chatMessages.innerHTML = '<div class="message ia">❌ Erreur lors du chargement de la discussion.</div>';
    }
}

function nouvelleDiscussion() {
    conversationActive = null;
    const chatMessages = document.getElementById('chatMessages');
    if (chatMessages) {
        chatMessages.innerHTML = `
            <div class="message ia">
                Bonjour ! Je suis LIA. Posez-moi une question sur vos cours ou ajoutez un document PDF.
            </div>
        `;
    }
    annulerFichier();
    chargerListeConversations();
}

function gererFichier(input) {
    const filePreview = document.getElementById('filePreview');
    const fileName = document.getElementById('fileName');
    if (input.files && input.files[0]) {
        fichierSelectionne = input.files[0];
        if (fileName) fileName.textContent = fichierSelectionne.name;
        if (filePreview) filePreview.style.display = 'flex';
    }
}

function annulerFichier() {
    fichierSelectionne = null;
    const fileInput = document.getElementById('fileInput');
    const filePreview = document.getElementById('filePreview');
    if (fileInput) fileInput.value = '';
    if (filePreview) filePreview.style.display = 'none';
}

function afficherMessage(texte, role) {
    const div = document.createElement('div');
    div.className = `message ${role}`;
    div.textContent = texte;
    const chatMessages = document.getElementById('chatMessages');
    if (chatMessages) {
        chatMessages.appendChild(div);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
}

function afficherTyping() {
    const div = document.createElement('div');
    div.id = 'typingIndicator';
    div.className = 'message ia typing';
    div.innerHTML = '<span>.</span><span>.</span><span>.</span>';
    const chatMessages = document.getElementById('chatMessages');
    if (chatMessages) {
        chatMessages.appendChild(div);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
}

function retirerTyping() {
    document.getElementById('typingIndicator')?.remove();
}

async function sendMessage() {
    const userInput = document.getElementById('userInput');
    const question = userInput.value.trim();
    if (!question && !fichierSelectionne) return;

    if (fichierSelectionne) {
        afficherMessage(`📁 Document joint : ${fichierSelectionne.name}`, 'user');
        afficherTyping();

        const formData = new FormData();
        formData.append('fichier', fichierSelectionne);
        formData.append('titre', fichierSelectionne.name);

        try {
            const resFile = await fetch('/ressource/ajouter/', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCookie('csrftoken')
                },
                body: formData
            });
            const dataFile = await resFile.json();
            retirerTyping();

            if (dataFile.status === 'success') {
                afficherMessage(`✅ Document indexé ${dataFile.ia || ''}`, 'ia');
            } else {
                afficherMessage(`⚠️ Erreur d'indexation : ${dataFile.erreur || 'Échec du traitement'}`, 'ia');
            }
        } catch (e) {
            retirerTyping();
            afficherMessage("⚠️ Erreur réseau lors de l'envoi du fichier.", 'ia');
        }
        annulerFichier();
    }

    if (question) {
        afficherMessage(question, 'user');
        userInput.value = '';
        userInput.style.height = 'auto';

        afficherTyping();

        try {
            const response = await fetch('/assistant_ia/', {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken')
                },
                body: JSON.stringify({
                    question: question,
                    conversation_id: conversationActive
                })
            });

            const data = await response.json();
            retirerTyping();

            if (data.reponse) {
                afficherMessage(data.reponse, 'ia');
                if (data.conversation_id) {
                    conversationActive = data.conversation_id;
                    chargerListeConversations();
                }
            } else {
                afficherMessage("❌ " + (data.erreur || "Une erreur est survenue."), 'ia');
            }
        } catch (err) {
            retirerTyping();
            afficherMessage("❌ Erreur de connexion au serveur.", 'ia');
        }
    }
}

const textarea = document.getElementById('userInput');
if (textarea) {
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
}
