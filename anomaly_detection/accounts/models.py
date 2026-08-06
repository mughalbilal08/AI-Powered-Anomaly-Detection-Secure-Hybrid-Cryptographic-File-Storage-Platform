import base64
import hashlib
from django.db import models
from django.contrib.auth.models import User
from django_otp.plugins.otp_email.models import EmailDevice
from django.utils import timezone
from django.conf import settings

class CustomEmailDevice(EmailDevice):
    token_created_at = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if self.token and not self.token_created_at:
            self.token_created_at = timezone.now()
        super().save(*args, **kwargs)

    def verify_token(self, token):
        if not self.token or not self.token_created_at:
            return False

        validity = getattr(settings, 'OTP_EMAIL_TOKEN_VALIDITY', 600)
        time_elapsed = (timezone.now() - self.token_created_at).total_seconds()
        if time_elapsed > validity:
            return False

        if token == self.token:
            self.token_created_at = None
            self.token = None
            self.save()
            return True

        return False


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    email_verified = models.BooleanField(default=False)
    private_key = models.BinaryField(blank=True, null=True)
    public_key = models.BinaryField(blank=True, null=True)
    otp_verification_count = models.IntegerField(default=0)
    login_attempts = models.IntegerField(default=0)
    otp_attempts = models.IntegerField(default=0)

    def __str__(self):
        return self.user.username

    def generate_key_pair(self, user_password):
        from accounts.services.crypto_service import generate_user_key_pair
        public_pem, encrypted_private_key = generate_user_key_pair(user_password)
        self.public_key = public_pem
        self.private_key = encrypted_private_key
        self.save()

    def get_private_key(self, user_password):
        from accounts.services.crypto_service import get_user_private_key
        return get_user_private_key(self, user_password)


class ActivityLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    ip_address = models.CharField(max_length=45)
    latitude = models.FloatField()
    longitude = models.FloatField()
    city = models.CharField(max_length=100, blank=True, null=True)
    country = models.CharField(max_length=100, blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    action = models.CharField(max_length=20, choices=[
        ('login', 'Login'),
        ('upload', 'Upload'),
        ('share', 'Share'),
        ('download', 'Download')
    ])
    is_anomaly = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.username} - {self.action} at {self.timestamp}"


class SecureFile(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='owned_files')
    file = models.FileField(upload_to='secure_files/')
    original_filename = models.CharField(max_length=255)
    encrypted_key = models.BinaryField()
    uploaded_at = models.DateTimeField(auto_now_add=True)
    file_hash = models.CharField(max_length=64, blank=True, null=True)
    file_size = models.BigIntegerField(blank=True, null=True)
    file_type = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return f"{self.original_filename} (Owner: {self.owner.username})"

    def encrypt_and_save(self, file_content, user_password):
        from accounts.services.crypto_service import encrypt_and_save_file
        encrypt_and_save_file(self, file_content, user_password)

    def get_file_key(self, user_password):
        from accounts.services.crypto_service import get_file_key_for_owner
        return get_file_key_for_owner(self, user_password)

    def decrypt(self, user_password):
        from accounts.services.crypto_service import decrypt_file_for_owner
        return decrypt_file_for_owner(self, user_password)


class FileShare(models.Model):
    file = models.ForeignKey(SecureFile, on_delete=models.CASCADE, related_name='shares')
    shared_with = models.ForeignKey(User, on_delete=models.CASCADE, related_name='shared_files')
    shared_at = models.DateTimeField(auto_now_add=True)
    encrypted_key = models.BinaryField(null=True, blank=True)
    expiration_date = models.DateTimeField(null=True, blank=True)
    is_revoked = models.BooleanField(default=False)

    class Meta:
        unique_together = ('file', 'shared_with')

    def __str__(self):
        return f"{self.file.original_filename} shared with {self.shared_with.username}"


class FileDownload(models.Model):
    file = models.ForeignKey(SecureFile, on_delete=models.CASCADE, related_name='downloads')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='file_downloads')
    downloaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('file', 'user', 'downloaded_at')

    def __str__(self):
        return f"{self.file.original_filename} downloaded by {self.user.username} at {self.downloaded_at}"