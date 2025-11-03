from django.test import TestCase
from core.rsa_utils.rsa_manager import RSAKeyManager
import base64

class RSATest(TestCase):
    def test_encryption_and_decryption(self):
        manager, pub = RSAKeyManager.generate_keys()
        message = b"Hello world!"
        ciphertext = manager.encrypt(pub, message)
        print(base64.b64encode(ciphertext).decode('ascii'))
        plaintext = manager.decrypt(ciphertext)
        print(plaintext)
        self.assertEqual(plaintext, message)
