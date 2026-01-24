let CURRENT_PEM_CONTENT = null;
// ###########################################################################################
// # End-to-End Decryption (E2EE) Engine
// ###########################################################################################

document.addEventListener("DOMContentLoaded", () => {
    const fileInput = document.getElementById('private-key-file');
    const statusText = document.getElementById('decryption-status');

    fileInput.addEventListener('change', async (e) => {
        const file = e.target.files[0];
        if (!file) return;

        const reader = new FileReader();
        reader.onload = async (event) => {
            // Saving PK to memeory
            CURRENT_PEM_CONTENT = event.target.result;
            
            // First decryption for all messages
            decryptAllMessages(CURRENT_PEM_CONTENT, statusText);
        };
        reader.readAsText(file);
    });

    document.addEventListener('messages-appended', () => {
        if (CURRENT_PEM_CONTENT) {
            decryptAllMessages(CURRENT_PEM_CONTENT, statusText);
        }
    });
});

// ###########################################################################################
// # Hybrid decryption
// ###########################################################################################
async function decryptE2EE(ciphertextB64, encryptedAesKeyB64, ivB64, privateKey) {
    // Decrypting AES key with RSA
    const encryptedAesKeyBuffer = base64ToBuffer(encryptedAesKeyB64);
    const aesKeyRaw = await window.crypto.subtle.decrypt(
        { name: "RSA-OAEP" },
        privateKey,
        encryptedAesKeyBuffer
    );

    // Importing decrypted AES key
    const aesKey = await window.crypto.subtle.importKey(
        "raw", aesKeyRaw, { name: "AES-GCM" }, false, ["decrypt"]
    );

    // decrypting ciphertext
    const ciphertextBuffer = base64ToBuffer(ciphertextB64);
    const iv = base64ToBuffer(ivB64);
    
    const decryptedBuffer = await window.crypto.subtle.decrypt(
        { name: "AES-GCM", iv: iv },
        aesKey,
        ciphertextBuffer
    );

    return new TextDecoder().decode(decryptedBuffer);
}

// Imports PK PKCS#8 from .PEM
async function importPrivateKey(pem) {
    const b64 = pem.replace(/-----BEGIN PRIVATE KEY-----|-----END PRIVATE KEY-----|\s/g, "");
    const binary = atob(b64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
    
    return await window.crypto.subtle.importKey(
        "pkcs8", bytes.buffer, 
        { name: "RSA-OAEP", hash: "SHA-256" }, 
        false, ["decrypt"]
    );
}

function base64ToBuffer(b64) {
    const binary = atob(b64);
    return Uint8Array.from(binary, c => c.charCodeAt(0)).buffer;
}



async function decryptAllMessages(privateKeyPem, statusText) {
    try {
        // Get all messages
        const allEncryptedMessages = document.querySelectorAll('.encrypted-msg');
        
        if (allEncryptedMessages.length === 0) {
            console.error("Błąd: Nie znaleziono żadnych wiadomości do odszyfrowania!");
            return;
        }

        // PK import
        const privKey = await importPrivateKey(privateKeyPem);
        statusText.innerHTML = '<span class="text-success">Key loaded. Decrypting...</span>';
        
        // decryption loop
        for (let el of allEncryptedMessages) {
            try {
                const decrypted = await decryptE2EE(
                    el.dataset.ciphertext,
                    el.dataset.aesKey,
                    el.dataset.iv,
                    privKey
                );

                // changing html text
                el.innerHTML = decrypted;
                // removing class so it wont be decrypted again
                el.classList.remove('encrypted-msg'); 
                el.style.color = "inherit";
            } catch (singleErr) {
                console.warn("Couldn't decrypt message (maybe wrong key)", singleErr);
            }
            statusText.innerHTML = '<span class="text-success">Messages decrypted.</span>';
        }
    } catch (err) {
        console.error("Critical error:", err.message);
        statusText.innerHTML = '<span class="text-danger">Key or data format error.</span>';
    }
}