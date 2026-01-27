let lastMessageId = CHAT_CONFIG.lastMessageId;

document.addEventListener("DOMContentLoaded", () => {
    scrollToBottom();
})

function checkNewMessages() {
    fetch(`${CHAT_CONFIG.urlGetNewMessages}?last_message_id=${lastMessageId}`, {
        headers: {
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        if (data.messages.length > 0) {
            const container = document.getElementById('message-container');
            
            data.messages.forEach(msg => {
                const isCurrentUser = msg.sender__id === CHAT_CONFIG.currentUserId;
                const messageDiv = document.createElement('div');
                messageDiv.className = `message mb-3 ${isCurrentUser ? 'text-end' : ''}`;
                
                const safeAesKey = (msg.encrypted_aes_key && msg.encrypted_aes_key !== 'None') ? msg.encrypted_aes_key : '';
                const safeIv = (msg.iv && msg.iv !== 'None') ? msg.iv : '';
                
                let contentHTML = '';


                if (!safeAesKey) {
                     contentHTML = `<span class="small fst-italic text-muted">(Wiadomość archiwalna - brak klucza)</span>`;
                } else {
                     contentHTML = `
                        <span class="encrypted-msg" 
                              data-ciphertext="${msg.ciphertext}" 
                              data-aes-key="${safeAesKey}" 
                              data-iv="${safeIv}">
                              ${msg.ciphertext}
                        </span>`;
                }

                const timestamp = new Date(msg.timestamp).toLocaleString();
                
                messageDiv.innerHTML = `
                    <div class="d-inline-block" style="max-width: 70%;">
                        <div class="p-2 rounded ${isCurrentUser ? 'bg-primary text-white' : 'bg-light'}">
                            <strong>${msg.sender__username}</strong><br>
                            ${contentHTML}
                        </div>
                        <small class="text-muted">${timestamp}</small>
                    </div>
                `;
                
                container.appendChild(messageDiv);
                lastMessageId = msg.id;
            });

            if (data.messages.length > 0) {
                container.scrollTop = container.scrollHeight;
                const event = new CustomEvent('messages-appended');
                document.dispatchEvent(event);
            }
        }
    })
    .catch(e => console.error("Błąd pobierania wiadomości:", e));
}
function scrollToBottom() {
    const container = document.getElementById('message-container');
    if (container) {
        container.scrollTop = container.scrollHeight;
    }
}

setInterval(checkNewMessages, 3000);