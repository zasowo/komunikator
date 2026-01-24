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
// # Converts pub key into usable crypto obj. Uses RSA-OAEP. Encryption only.
// # Generates AES Session Key + IV then encrypts plaintext with it.
// # Last step is to encrypt AES key with RSA.
// ###########################################################################################
async function performE2EE(plainText, pubKeyPem) {
    // Pub key import
    const rsaKey = await window.crypto.subtle.importKey(
        "spki",
        pemToArrayBuffer(pubKeyPem),
        { name: "RSA-OAEP", hash: "SHA-256" },
        false,
        ["encrypt"]
    );

    // Generating random AES key and IV
    const aesKey = await window.crypto.subtle.generateKey(
        { name: "AES-GCM", length: 256 },
        true,
        ["encrypt"]
    );
    const iv = window.crypto.getRandomValues(new Uint8Array(12));

    // Encryptin plaintext with AES
    const encodedText = new TextEncoder().encode(plainText);
    const ciphertextBuffer = await window.crypto.subtle.encrypt(
        { name: "AES-GCM", iv: iv },
        aesKey,
        encodedText
    );

    // Encrypting AES with RSA
    const exportedAesKey = await window.crypto.subtle.exportKey("raw", aesKey);
    const encryptedAesKeyBuffer = await window.crypto.subtle.encrypt(
        { name: "RSA-OAEP" },
        rsaKey,
        exportedAesKey
    );

    return {
        ciphertext: bufferToBase64(ciphertextBuffer),
        aes_key: bufferToBase64(encryptedAesKeyBuffer),
        iv: bufferToBase64(iv)
    };
}
// ###########################################################################################



// ###########################################################################################
// # End-to-End Encryption (E2EE) Engine
// ###########################################################################################
document.addEventListener("DOMContentLoaded", () => {
    const sendBtn = document.getElementById('send-secure-btn');
    const rawInput = document.getElementById('raw-message-input');
    const messageForm = document.getElementById('message-form');

    if (!sendBtn) {
        console.error("no send-secure-btn. THAT SHOULD NOT HAPPEN LOL");
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

        try {
            sendBtn.disabled = true;
            sendBtn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Encrypting...';

            // Encryption fun.
            const encryptedPackage = await performE2EE(text, RECIPIENT_PUBLIC_KEY);

            // Prepearing data to send (AJAX)
            const formData = new FormData();
            formData.append('ciphertext', encryptedPackage.ciphertext);
            formData.append('encrypted_aes_key', encryptedPackage.aes_key);
            formData.append('iv', encryptedPackage.iv);
            
            const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
            formData.append('csrfmiddlewaretoken', csrfToken);

            // ASYNC SEND. Instead of submit, we are using fetch to not clear PK from memory
            const response = await fetch(window.location.href, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });

            if (response.ok) {
                rawInput.value = '';
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
// ###########################################################################################