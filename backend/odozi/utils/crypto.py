import os
from cryptography.fernet import Fernet
from django.conf import settings

# This key lives ONLY in your .env file, NEVER in the code or DB
# cipher_suite = Fernet(os.getenv("TOKEN_ENCRYPTION_KEY").encode())
cipher_suite = Fernet(settings.TOKEN_ENCRYPTION_KEY.encode())

def encrypt_token(raw_token_str):
    if not raw_token_str:
        return None
    return cipher_suite.encrypt(raw_token_str.encode())

def decrypt_token(encrypted_bytes):
    if not encrypted_bytes:
        return ""
    return cipher_suite.decrypt(bytes(encrypted_bytes)).decode()
