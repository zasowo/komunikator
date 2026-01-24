let lastMessageId = CHAT_CONFIG.lastMessageId;

document.addEventListener("DOMContentLoaded", () => {
    scrollToBottom();
})

function checkNewMessages() {
    fetch(`${CHAT_CONFIG.urlGetNewMessages}?last_message_id=${lastMessageId}`)
        .then(response => response.json())
        .then(data => {
            if (data.messages.length > 0) {
                const container = document.getElementById('message-container');
                
                data.messages.forEach(msg => {
                    const isCurrentUser = msg.sender__id === CHAT_CONFIG.currentUserId;
                    const messageDiv = document.createElement('div');
                    messageDiv.className = `message mb-3 ${isCurrentUser ? 'text-end' : ''}`;
                    
                    let content;
                    if (isCurrentUser) {
                        content = '<span class="small">Your secure message</span>';
                    } else {
                        content = `
                            <span class="encrypted-msg" 
                                  data-ciphertext="${msg.ciphertext}" 
                                  data-aes-key="${msg.encrypted_aes_key}" 
                                  data-iv="${msg.iv}">
                                  ${msg.ciphertext}
                            </span>`;
                    }

                    const timestamp = new Date(msg.timestamp).toLocaleString();
                    
                    messageDiv.innerHTML = `
                        <div class="d-inline-block" style="max-width: 70%;">
                            <div class="p-2 rounded ${isCurrentUser ? 'bg-primary text-white' : 'bg-light'}">
                                <strong>${msg.sender__username}</strong><br>
                                ${content}
                            </div>
                            <small class="text-muted">${timestamp}</small>
                        </div>
                    `;
                    
                    container.appendChild(messageDiv);
                    lastMessageId = msg.id;
                });

                container.scrollTop = container.scrollHeight;

                if (data.messages.length > 0) {
                    container.scrollTop = container.scrollHeight;
                    const event = new CustomEvent('messages-appended');
                    document.dispatchEvent(event);
                }
            }
        });
}

function scrollToBottom() {
    const container = document.getElementById('message-container');
    if (container) {
        container.scrollTop = container.scrollHeight;
    }
}

setInterval(checkNewMessages, 3000);