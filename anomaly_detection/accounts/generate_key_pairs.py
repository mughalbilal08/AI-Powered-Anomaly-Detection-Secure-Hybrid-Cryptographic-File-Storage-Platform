# anomaly_detection/accounts/generate_key_pairs.py
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.fernet import Fernet
import base64
import os

def generate_key_pair(user_password):
    """
    Generates an RSA key pair and encrypts the private key with the user's password.
    Args:
        user_password (str): The user's password to encrypt the private key.
    Returns:
        tuple: (public_key, private_key) where:
            - public_key is the serialized public key (bytes).
            - private_key is the encrypted private key (bytes, with salt prepended).
    """
    print("Generating RSA key pair in generate_key_pairs.py")
    try:
        # Generate RSA key pair
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048
        )
        public_key = private_key.public_key()
        print("RSA key pair generated successfully")

        # Serialize the public key
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        print("Public key serialized")

        # Serialize the private key
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        print("Private key serialized")

        # Encrypt the private key with the user's password
        password = user_password.encode()
        print(f"Password encoded, length: {len(password)}")
        if not password:
            raise ValueError("User password cannot be empty")

        salt = os.urandom(16)
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password))
        print(f"Derived key: {key.decode()}")
        fernet = Fernet(key)
        print("Fernet instance created")
        encrypted_private_key = fernet.encrypt(private_pem)
        print("Private key encrypted")

        # Return the public key and the salt + encrypted private key
        return public_pem, salt + encrypted_private_key
    except Exception as e:
        print(f"Error in generate_key_pair: {e}")
        raise