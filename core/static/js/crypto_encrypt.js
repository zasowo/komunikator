// ###########################################################################################
// # End-to-End Encryption (E2EE) Engine
// ###########################################################################################

function pemToArrayBuffer(pem) {
    const b64 = pem.replace(/-----BEGIN PUBLIC KEY-----|-----END PUBLIC KEY-----|\s/g, "");
    return Uint8Array.from(atob(b64), c => c.charCodeAt(0)).buffer;
}

function bufferToBase64(buf) {
    return btoa(String.fromCharCode(...new Uint8Array(buf)));
}

// ###########################################################################################
// # Converts pub keys into usable crypto obj. Uses RSA-OAEP. Encryption only.
// # Generates AES Session Key + IV then encrypts plaintext with it.
// # Last step is to encrypt AES key with RSA (TWICE: for recipient and sender).
// ###########################################################################################
async function performE2EE(plainText, recipientPubKeyPem, senderPubKeyPem) {
    const recipientRsaKey = await window.crypto.subtle.importKey(
        "spki",
        pemToArrayBuffer(recipientPubKeyPem),
        { name: "RSA-OAEP", hash: "SHA-256" },
        false,
        ["encrypt"]
    );

    const senderRsaKey = await window.crypto.subtle.importKey(
        "spki",
        pemToArrayBuffer(senderPubKeyPem),
        { name: "RSA-OAEP", hash: "SHA-256" },
        false,
        ["encrypt"]
    );

    const aesKey = await window.crypto.subtle.generateKey(
        { name: "AES-GCM", length: 256 },
        true,
        ["encrypt"]
    );
    const iv = window.crypto.getRandomValues(new Uint8Array(12));

    const encodedText = new TextEncoder().encode(plainText);
    const ciphertextBuffer = await window.crypto.subtle.encrypt(
        { name: "AES-GCM", iv: iv },
        aesKey,
        encodedText
    );

    const exportedAesKey = await window.crypto.subtle.exportKey("raw", aesKey);

    const encryptedAesKeyForRecipient = await window.crypto.subtle.encrypt(
        { name: "RSA-OAEP" },
        recipientRsaKey,
        exportedAesKey
    );

    const encryptedAesKeyForSender = await window.crypto.subtle.encrypt(
        { name: "RSA-OAEP" },
        senderRsaKey,
        exportedAesKey
    );

    return {
        ciphertext: bufferToBase64(ciphertextBuffer),
        aes_key_recipient: bufferToBase64(encryptedAesKeyForRecipient),
        aes_key_sender: bufferToBase64(encryptedAesKeyForSender),
        iv: bufferToBase64(iv)
    };
}
// ###########################################################################################


document.addEventListener("DOMContentLoaded", () => {
    const sendBtn = document.getElementById('send-secure-btn');
    const rawInput = document.getElementById('raw-message-input');

    if (!sendBtn) {
        console.error("no send-secure-btn found.");
        return;
    }

    sendBtn.addEventListener('click', async (e) => {
        e.preventDefault(); // preventing default send
        
        const text = rawInput.value.trim();
        if (!text) return;

        // Validating receiver public key.
        if (typeof RECIPIENT_PUBLIC_KEY === 'undefined' || !RECIPIENT_PUBLIC_KEY || RECIPIENT_PUBLIC_KEY.includes('Brak')) {
            alert("The recipient does not have a public key. Secure sending is impossible.");
            return;
        }

        // Validating sender public key (NEW CHECK)
        if (typeof SENDER_PUBLIC_KEY === 'undefined' || !SENDER_PUBLIC_KEY) {
            alert("You do not have a public key generated. Please go to settings and generate one to see your own messages.");
            return;
        }

        try {
            sendBtn.disabled = true;
            sendBtn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Encrypting...';

            // Encryption fun. (Passing both keys now)
            const encryptedPackage = await performE2EE(text, RECIPIENT_PUBLIC_KEY, SENDER_PUBLIC_KEY);

            // Preparing data to send (AJAX)
            const formData = new FormData();
            formData.append('ciphertext', encryptedPackage.ciphertext);
            
            // We send BOTH encrypted keys
            formData.append('encrypted_aes_key', encryptedPackage.aes_key_recipient);
            formData.append('encrypted_aes_key_sender', encryptedPackage.aes_key_sender);
            
            formData.append('iv', encryptedPackage.iv);
            
            const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
            formData.append('csrfmiddlewaretoken', csrfToken);

            // ASYNC SEND.
            const response = await fetch(window.location.href, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });

            if (response.ok) {
                rawInput.value = '';
                if (typeof checkNewMessages === "function") {
                    checkNewMessages();
                }
            } else {
                throw new Error("The server rejected the package");
            }

        } catch (err) {
            console.error("Encryption/Send Error:", err);
            alert("Error: " + err.message);
        } finally {
            sendBtn.disabled = false;
            sendBtn.textContent = "Send";
        }
    });
});