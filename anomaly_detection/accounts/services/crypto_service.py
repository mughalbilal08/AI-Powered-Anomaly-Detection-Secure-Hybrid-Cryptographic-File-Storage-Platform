import base64
import hashlib
import hmac
import os
from django.conf import settings
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

def generate_user_key_pair(user_password):
    """
    Generates an RSA key pair and encrypts the private key with the user's password.
    Returns (public_pem, salt_and_encrypted_private_key).
    """
    if not user_password:
        raise ValueError("User password cannot be empty")

    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048
    )
    public_key = private_key.public_key()

    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )

    password_bytes = user_password.encode('utf-8')
    salt = os.urandom(16)
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(password_bytes))
    fernet = Fernet(key)
    encrypted_private_key = fernet.encrypt(private_pem)

    return public_pem, salt + encrypted_private_key


def get_user_private_key(user_profile, user_password):
    """
    Decrypts and returns the RSA private key object for a user using their password.
    """
    if not user_profile.private_key:
        raise ValueError("Private key not found")

    salt = user_profile.private_key[:16]
    encrypted_private_key = user_profile.private_key[16:]

    password_bytes = user_password.encode('utf-8')
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(password_bytes))
    fernet = Fernet(key)

    try:
        private_pem = fernet.decrypt(encrypted_private_key)
    except Exception:
        raise ValueError("Invalid password for private key decryption")

    return serialization.load_pem_private_key(private_pem, password=None)


def encrypt_and_save_file(secure_file, file_content, user_password):
    """
    Encrypts file content with a symmetric Fernet key, encrypts the key with owner's RSA public key,
    writes the file to disk, and updates model fields.
    """
    from accounts.models import UserProfile

    file_hash = hashlib.sha256(file_content).hexdigest()
    file_key = Fernet.generate_key()
    fernet = Fernet(file_key)
    encrypted_content = fernet.encrypt(file_content)

    owner_profile = UserProfile.objects.get(user=secure_file.owner)
    if not owner_profile.public_key:
        raise ValueError("Owner does not have an RSA public key")

    public_key = serialization.load_pem_public_key(owner_profile.public_key)
    encrypted_file_key = public_key.encrypt(
        file_key,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )

    with open(secure_file.file.path, 'wb') as f:
        f.write(encrypted_content)

    secure_file.file_hash = file_hash
    secure_file.encrypted_key = encrypted_file_key
    secure_file.save()


def get_file_key_for_owner(secure_file, user_password):
    """
    Decrypts the file key using the owner's RSA private key.
    """
    from accounts.models import UserProfile

    owner_profile = UserProfile.objects.get(user=secure_file.owner)
    private_key = get_user_private_key(owner_profile, user_password)

    try:
        file_key = private_key.decrypt(
            secure_file.encrypted_key,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        return file_key
    except Exception:
        raise ValueError("Invalid password or corrupted key")


def decrypt_file_for_owner(secure_file, user_password):
    """
    Decrypts and returns the original file content for the file owner.
    """
    file_key = get_file_key_for_owner(secure_file, user_password)
    fernet = Fernet(file_key)

    with open(secure_file.file.path, 'rb') as f:
        encrypted_content = f.read()

    decrypted_content = fernet.decrypt(encrypted_content)
    computed_hash = hashlib.sha256(decrypted_content).hexdigest()
    if computed_hash != secure_file.file_hash:
        raise ValueError("File integrity check failed: content has been modified")

    return decrypted_content


def encrypt_file_key_for_recipient(file_key, recipient_user):
    """
    Encrypts a file symmetric key using the recipient's RSA public key.
    """
    from accounts.models import UserProfile

    recipient_profile = UserProfile.objects.get(user=recipient_user)
    if not recipient_profile.public_key:
        raise ValueError("Recipient does not have a user profile or public key.")

    public_key = serialization.load_pem_public_key(recipient_profile.public_key)
    return public_key.encrypt(
        file_key,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )


def decrypt_file_for_recipient(file_share, user_password):
    """
    Decrypts file content for a user with whom the file was shared.
    """
    from accounts.models import UserProfile

    recipient_profile = UserProfile.objects.get(user=file_share.shared_with)
    private_key = get_user_private_key(recipient_profile, user_password)

    file_key = private_key.decrypt(
        file_share.encrypted_key,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )

    fernet = Fernet(file_key)
    with open(file_share.file.file.path, 'rb') as f:
        encrypted_content = f.read()

    return fernet.decrypt(encrypted_content)


def generate_share_hmac(message):
    """
    Generates an HMAC-SHA256 signature for verification in email notifications.
    """
    hmac_secret = getattr(settings, 'HMAC_SECRET', settings.SECRET_KEY.encode('utf-8'))
    hmac_obj = hmac.new(hmac_secret, message.encode('utf-8'), hashlib.sha256)
    return base64.urlsafe_b64encode(hmac_obj.digest()).decode('utf-8')
