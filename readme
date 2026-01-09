# Zero-Trust E2EE Messenger

This is a secure communication platform built with a **Zero-Trust** security architecture. The application ensures that the server never has access to the plaintext content of messages by implementing true End-to-End Encryption (E2EE).

---

## Core Concept: Zero-Trust

In this model, the server is treated as a potentially compromised or untrusted entity. It only acts as a storage and relay for encrypted "blobs". All cryptographic operations (encryption and decryption) happen exclusively in the user's browser using the **Web Crypto API**.

---

## Quick Start

### 1. Prerequisites

Ensure you have Python 3.x installed on your system.

### 2. Installation

Clone the repository and install the required dependencies:

```bash
git clone ...
cd <project-folder>
pip install -r requirements.txt
```

### 3. Database Setup

Apply migrations to set up your local database:

```bash
python manage.py migrate
```

### 4. Run the Application

Start the development server:

```bash
python manage.py runserver
```

Navigate to [http://127.0.0.1:8000](http://127.0.0.1:8000) in your web browser (FOR TESTS).

---

## Security & Key Management

### Getting Started with Communication

To start receiving secure messages, a user must first set up their cryptographic identity:

* **Key Generation**: Go to *User Settings* and generate a new RSA Key Pair.
* **Public Key**: Your public key is automatically uploaded to the server so others can encrypt messages for you.
* **Private Key**: Your private key is downloaded as a `.pem` file. The server never receives a copy of this file.

### Handling the Private Key (Critical)

* **Confidentiality**: You must keep your `.pem` file safe and private.
* **Decryption**: To read messages, you must upload your local `.pem` file to the chat interface. It is stored only in the browser's RAM and is lost upon refreshing or closing the tab.
* **Key Loss**: If you lose your private key file, you cannot recover your old messages. They are encrypted for that specific key and will remain secret forever.
* **Key Rotation**: You can generate a new key set at any time, but it will only apply to new incoming messages.

---

## Tech Stack

* **Backend**: Django (Python)
* **Frontend**: JavaScript (Web Crypto API)
* **Database**: SQLite (Development) / PostgreSQL (Production)
* **Encryption**: Hybrid RSA-OAEP (2048-bit) + AES-GCM (256-bit)

---

## GRUG Context

> **Note**: Strong Bus & Grug & Grug the Great.
