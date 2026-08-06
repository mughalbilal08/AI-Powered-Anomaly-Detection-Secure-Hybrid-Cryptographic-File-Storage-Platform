import json
import random
from datetime import timedelta
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Count
from django.db.models.functions import TruncDay, TruncHour
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.forms import (
    FileDownloadForm,
    FileShareForm,
    FileUploadForm,
    OTPVerificationForm,
    UserLoginForm,
    UserSignupForm,
)
from accounts.models import (
    ActivityLog,
    CustomEmailDevice,
    FileDownload,
    FileShare,
    SecureFile,
    UserProfile,
)
from accounts.services import crypto_service, location_service, ml_service
from accounts.services.activity_service import record_activity, send_user_email


def home(request):
    """Render home landing page."""
    return render(request, 'home.html')


def signup(request):
    """User registration view."""
    if request.method == 'POST':
        form = UserSignupForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']

            user = User.objects.create_user(username=username, email=email, password=password)
            user_profile = UserProfile.objects.create(user=user)
            
            # Generate cryptographic RSA key pair for user
            crypto_service.generate_user_key_pair(password)
            user_profile.generate_key_pair(password)

            messages.success(request, 'Account created successfully. Please log in.')
            return redirect('login')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, error)
    else:
        form = UserSignupForm()

    return render(request, 'signup.html', {'form': form})


def login_view(request):
    """User authentication view with adaptive MFA / OTP triggering."""
    if request.method == 'POST':
        form = UserLoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            user = authenticate(request, username=username, password=password)

            if user:
                ip_address = location_service.get_ip_address(request)
                latitude, longitude, city, country, location_retrieved = location_service.get_location_data(request, ip_address)

                request.session['latitude'] = latitude
                request.session['longitude'] = longitude
                request.session['city'] = city
                request.session['country'] = country

                device_type = location_service.get_device_type(request)
                profile, _ = UserProfile.objects.get_or_create(user=user)
                requires_otp = False

                if profile.otp_verification_count < 4:
                    requires_otp = True
                else:
                    model_anomaly = bool(ml_service.predict_activity_anomaly(
                        ip_address, latitude, longitude, 'login', device_type
                    ))
                    if model_anomaly or not location_retrieved:
                        requires_otp = True

                record_activity(request, user, 'login', requires_otp=requires_otp)

                if requires_otp:
                    device, _ = CustomEmailDevice.objects.get_or_create(user=user, name='email')
                    current_time = timezone.now()
                    validity = getattr(settings, 'OTP_EMAIL_TOKEN_VALIDITY', 600)

                    time_elapsed = (current_time - device.token_created_at).total_seconds() if (device.token and device.token_created_at) else float('inf')

                    if not device.token or time_elapsed > validity:
                        otp = str(random.randint(100000, 999999))
                        device.token = otp
                        device.token_created_at = current_time
                        device.save()

                        try:
                            send_user_email(
                                subject='Your OTP Security Code',
                                message=f'Your OTP is {otp}. Valid for 10 minutes.',
                                recipient_email=user.email
                            )
                            messages.success(request, 'OTP has been sent to your email.')
                        except Exception as e:
                            messages.error(request, f'Failed to send OTP: {e}')
                            return redirect('login')

                    request.session['user_id'] = user.id
                    return redirect('verify_otp')
                else:
                    login(request, user)
                    messages.success(request, 'Login successful!')
                    return redirect('dashboard')
            else:
                messages.error(request, 'Invalid credentials')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, error)
    else:
        form = UserLoginForm()

    return render(request, 'login.html', {'form': form})


def verify_otp(request):
    """OTP Verification view."""
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('login')

    user = get_object_or_404(User, id=user_id)

    if request.method == 'POST':
        form = OTPVerificationForm(request.POST)
        if form.is_valid():
            otp = form.cleaned_data['otp']
            try:
                device = CustomEmailDevice.objects.get(user=user, name='email')
            except CustomEmailDevice.DoesNotExist:
                messages.error(request, 'OTP device not found. Please log in again.')
                return redirect('login')

            if device.verify_token(otp):
                profile, _ = UserProfile.objects.get_or_create(user=user)
                profile.otp_verification_count += 1
                profile.email_verified = True
                profile.save()

                login(request, user)
                request.session.pop('user_id', None)
                messages.success(request, 'OTP verified successfully.')
                return redirect('dashboard')
            else:
                messages.error(request, 'Invalid or expired OTP')
        else:
            messages.error(request, 'Invalid OTP format.')
    else:
        form = OTPVerificationForm()

    return render(request, 'verify_otp.html', {'form': form})


@login_required
def dashboard(request):
    """User dashboard displaying logs, files, and activity metrics."""
    activity_log = ActivityLog.objects.filter(user=request.user).order_by('-timestamp')
    owned_files = SecureFile.objects.filter(owner=request.user)
    shared_files = FileShare.objects.filter(shared_with=request.user)

    uploads_by_hour = SecureFile.objects.filter(owner=request.user).annotate(
        hour=TruncHour('uploaded_at')
    ).values('hour').annotate(count=Count('id')).order_by('hour')

    shares_by_day = FileShare.objects.filter(file__owner=request.user).annotate(
        day=TruncDay('shared_at')
    ).values('day').annotate(count=Count('id')).order_by('day')

    downloads_by_day = FileDownload.objects.filter(
        user=request.user
    ).annotate(
        day=TruncDay('downloaded_at')
    ).values('day').annotate(count=Count('id')).order_by('day')

    total_downloads = FileDownload.objects.filter(user=request.user).count()

    uploads_data = [{'hour': str(item['hour']), 'count': item['count']} for item in uploads_by_hour]
    shares_data = [{'day': str(item['day']), 'count': item['count']} for item in shares_by_day]
    downloads_data = [{'day': str(item['day']), 'count': item['count']} for item in downloads_by_day]

    current_timestamp = int(timezone.now().timestamp())
    recent_threshold = 86400  # 24 hours
    has_recent_shares = any(
        current_timestamp <= int(share.shared_at.timestamp()) + recent_threshold and current_timestamp >= int(share.shared_at.timestamp())
        for share in shared_files
    )

    return render(request, 'dashboard.html', {
        'activity_log': activity_log,
        'owned_files': owned_files,
        'shared_files': shared_files,
        'encryption_message': 'This file was encrypted with a Fernet file_key, and the file_key was encrypted with your RSA public key.',
        'uploads_data': json.dumps(uploads_data),
        'shares_data': json.dumps(shares_data),
        'downloads_data': json.dumps(downloads_data),
        'total_downloads': total_downloads,
        'current_timestamp': current_timestamp,
        'has_recent_shares': has_recent_shares,
    })


@login_required
def logout_view(request):
    """User logout view."""
    logout(request)
    messages.success(request, 'Logged out successfully.')
    return redirect('login')


@login_required
def upload_file(request):
    """File upload and encryption view."""
    if request.method == 'POST':
        form = FileUploadForm(request.POST, request.FILES)
        if form.is_valid():
            uploaded_file = form.cleaned_data['file']
            password = form.cleaned_data['password']

            auth_user = authenticate(request, username=request.user.username, password=password)
            if not auth_user:
                messages.error(request, 'Invalid user password.')
                return redirect('dashboard')

            secure_file = SecureFile(
                owner=request.user,
                file=uploaded_file,
                original_filename=uploaded_file.name,
                file_size=uploaded_file.size,
                file_type=uploaded_file.content_type
            )
            secure_file.save()

            file_content = uploaded_file.read()
            crypto_service.encrypt_and_save_file(secure_file, file_content, password)

            record_activity(request, request.user, 'upload')
            messages.success(request, 'File encrypted and uploaded successfully.')
            return redirect('dashboard')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, error)
            return redirect('dashboard')

    return render(request, 'upload_file.html', {'form': FileUploadForm()})


@login_required
def share_file(request, file_id):
    """Secure file sharing view."""
    secure_file = get_object_or_404(SecureFile, id=file_id, owner=request.user)

    if request.method == 'POST':
        form = FileShareForm(request.POST)
        if form.is_valid():
            shared_with_email = form.cleaned_data['shared_with']
            owner_password = form.cleaned_data['password']

            try:
                recipient = User.objects.get(email__iexact=shared_with_email)
            except User.DoesNotExist:
                messages.error(request, 'User with this email does not exist.')
                return redirect('dashboard')
            except User.MultipleObjectsReturned:
                messages.error(request, 'Multiple users found with this email.')
                return redirect('dashboard')

            if recipient == request.user:
                messages.error(request, 'You cannot share a file with yourself.')
                return redirect('dashboard')

            if FileShare.objects.filter(file=secure_file, shared_with=recipient).exists():
                messages.error(request, 'File already shared with this user.')
                return redirect('dashboard')

            auth_user = authenticate(request, username=request.user.username, password=owner_password)
            if not auth_user:
                messages.error(request, 'Invalid password.')
                return redirect('dashboard')

            try:
                file_key = crypto_service.get_file_key_for_owner(secure_file, owner_password)
                encrypted_key_for_recipient = crypto_service.encrypt_file_key_for_recipient(file_key, recipient)
            except Exception as e:
                messages.error(request, f'Error encrypting key for recipient: {e}')
                return redirect('dashboard')

            expiration_date = timezone.now() + timedelta(days=7)
            file_share = FileShare.objects.create(
                file=secure_file,
                shared_with=recipient,
                encrypted_key=encrypted_key_for_recipient,
                expiration_date=expiration_date
            )

            # Generate HMAC verification
            message_text = f"File '{secure_file.original_filename}' has been shared with you by {request.user.username} on {file_share.shared_at}."
            hmac_value = crypto_service.generate_share_hmac(message_text)

            email_body = f"{message_text}\n\nHMAC for verification: {hmac_value}\n\nTo access the file, log in to the platform."
            try:
                send_user_email('New File Shared with You', email_body, recipient.email)
            except Exception as e:
                messages.warning(request, 'File shared successfully, but failed to send email notification.')

            record_activity(request, request.user, 'share')
            messages.success(request, f'File shared with {recipient.username} successfully.')
            return redirect('dashboard')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, error)
            return redirect('dashboard')

    return render(request, 'share_file.html', {'file': secure_file, 'form': FileShareForm()})


@login_required
def download_file(request, file_id):
    """File decryption and download view."""
    secure_file = get_object_or_404(SecureFile, id=file_id)
    is_owner = secure_file.owner == request.user
    is_shared = FileShare.objects.filter(file=secure_file, shared_with=request.user).exists()

    if not (is_owner or is_shared):
        messages.error(request, 'You do not have permission to access this file.')
        return redirect('dashboard')

    if is_shared:
        file_share = FileShare.objects.get(file=secure_file, shared_with=request.user)
        if file_share.is_revoked:
            messages.error(request, 'Access to this file has been revoked by the owner.')
            return redirect('dashboard')
        if file_share.expiration_date and timezone.now() > file_share.expiration_date:
            messages.error(request, 'This shared file link has expired.')
            return redirect('dashboard')

    if request.method == 'POST':
        form = FileDownloadForm(request.POST)
        if form.is_valid():
            password = form.cleaned_data['password']
            auth_user = authenticate(request, username=request.user.username, password=password)
            if not auth_user:
                messages.error(request, 'Invalid password.')
                return redirect('dashboard')

            try:
                if is_owner:
                    decrypted_content = crypto_service.decrypt_file_for_owner(secure_file, password)
                else:
                    file_share = FileShare.objects.get(file=secure_file, shared_with=request.user)
                    if not file_share.encrypted_key:
                        messages.error(request, 'File key not available. Please ask owner to re-share.')
                        return redirect('dashboard')
                    decrypted_content = crypto_service.decrypt_file_for_recipient(file_share, password)

                FileDownload.objects.create(file=secure_file, user=request.user)
                record_activity(request, request.user, 'download')

                response = HttpResponse(decrypted_content, content_type='application/octet-stream')
                response['Content-Disposition'] = f'attachment; filename="{secure_file.original_filename}"'
                return response

            except ValueError as e:
                messages.error(request, f'Decryption failed: {e}')
                return redirect('dashboard')
            except Exception as e:
                messages.error(request, f'Unexpected error during decryption: {e}')
                return redirect('dashboard')
        else:
            messages.error(request, 'Invalid form submission.')
            return redirect('dashboard')

    return render(request, 'download_file.html', {'file': secure_file, 'form': FileDownloadForm()})