document.addEventListener("DOMContentLoaded", () => {
    const btnGenerate = document.getElementById("btn-generate-js");
    const statusContainer = document.getElementById("js-status-container");
    const statusText = document.getElementById("js-status-text");
    const hiddenKeyStorage = document.getElementById("hidden-public-key-storage");
    const finalForm = document.getElementById("form-submit-public-key");

    if (!window.crypto || !window.crypto.subtle) {
        alert("Your browser does not support the Web Crypto API. Keys cannot be generated securely.");
        return;
    }

    btnGenerate.addEventListener("click", async () => {
        try {
            btnGenerate.disabled = true;
            statusContainer.style.display = "flex";
            statusText.textContent = "Generating a key pair...";

            // ###########################################################################################
            // # Generating keys with RSA-OAEP standart
            // ###########################################################################################
            const keyPair = await window.crypto.subtle.generateKey(
                {
                    name: "RSA-OAEP",
                    modulusLength: 2048, //TODO need to add selection for further use lol 
                    publicExponent: new Uint8Array([1, 0, 1]),
                    hash: "SHA-256",
                },
                true, // can export? (we need to save it)
                ["encrypt", "decrypt"]
            );

            statusText.textContent = "Exporting the private key...";

            // ###########################################################################################
            // # Private key export: using PKCS#8 format. Saving PK to .pem
            // ###########################################################################################
            const privateKeyBuffer = await window.crypto.subtle.exportKey("pkcs8", keyPair.privateKey);
            const privateKeyPEM = arrayBufferToPEM(privateKeyBuffer, "PRIVATE KEY");
            const now = new Date();
            const creationTime =
                now.getFullYear() + "-" +
                String(now.getMonth() + 1).padStart(2, "0") + "-" +
                String(now.getDate()).padStart(2, "0") + "_" +
                String(now.getHours()).padStart(2, "0") +
                String(now.getMinutes()).padStart(2, "0") +
                String(now.getSeconds()).padStart(2, "0");
                
            downloadStringAsFile(privateKeyPEM, "PK_" + creationTime+ ".pem");
            // ###########################################################################################

            // ###########################################################################################
            // # Public key export: using SPKI format. Sending key value to hiddenKeyStorage
            // ###########################################################################################
            statusText.textContent = "Sending the public key to the server...";

            const publicKeyBuffer = await window.crypto.subtle.exportKey("spki", keyPair.publicKey);
            const publicKeyPEM = arrayBufferToPEM(publicKeyBuffer, "PUBLIC KEY");

            hiddenKeyStorage.value = publicKeyPEM;

            // HARDCODED DELAY, FULLY PROFFESIOANL, TRUST ME
            setTimeout(() => {
                 finalForm.submit(); // <-- SERVER SUBMIT
            }, 1000);
            // ###########################################################################################
            
        } catch (err) {
            console.error(err);
            statusText.textContent = "Error: " + err.message;
            statusContainer.classList.remove("alert-info");
            statusContainer.classList.add("alert-danger");
            btnGenerate.disabled = false;
        }
    });

    // ###########################################################################################
    // # Converting binary data to Base64 and adding PEM headers
    // ###########################################################################################
    function arrayBufferToPEM(buffer, label) {
        let binary = '';
        const bytes = new Uint8Array(buffer);
        const len = bytes.byteLength;
        for (let i = 0; i < len; i++) {
            binary += String.fromCharCode(bytes[i]);
        }

        const base64 = window.btoa(binary); // base64 convertion
        const formattedBase64 = base64.match(/.{1,64}/g).join('\n'); // new line every 64 chars

        return `-----BEGIN ${label}-----\n${formattedBase64}\n-----END ${label}-----`;
    }
    // ###########################################################################################

    // ###########################################################################################
    // # Creating temporary blob and link and allowing user to download PK
    // ###########################################################################################
    function downloadStringAsFile(content, filename) {
        const blob = new Blob([content], { type: "application/x-pem-file" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        setTimeout(() => {
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);
        }, 0);
    }
    // ###########################################################################################
});