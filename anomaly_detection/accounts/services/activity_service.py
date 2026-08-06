from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings
from accounts.models import ActivityLog, UserProfile
from accounts.services.location_service import get_ip_address, get_device_type
from accounts.services.ml_service import predict_activity_anomaly

def record_activity(request, user, action, session_duration=300, requires_otp=False):
    """
    Records user activity (login, upload, share, download) and calculates anomaly status.
    """
    ip_address = get_ip_address(request)
    latitude = request.session.get('latitude', 0.0)
    longitude = request.session.get('longitude', 0.0)
    city = request.session.get('city') or 'Unknown'
    country = request.session.get('country') or 'Unknown'
    device_type = get_device_type(request)

    activity = ActivityLog(
        user=user,
        ip_address=ip_address,
        latitude=latitude,
        longitude=longitude,
        city=city,
        country=country,
        action=action
    )

    if action == 'login' and requires_otp:
        is_anomaly = True
    else:
        is_anomaly = bool(predict_activity_anomaly(ip_address, latitude, longitude, action, device_type, session_duration))

    activity.is_anomaly = is_anomaly
    activity.save()

    user_profile, _ = UserProfile.objects.get_or_create(user=user)
    if action == 'login':
        user_profile.login_attempts = (user_profile.login_attempts or 0) + 1
        user_profile.save()

    if activity.is_anomaly:
        messages.warning(request, f"Anomaly detected in your {action} activity. Please verify your account security.")

    return activity


def send_user_email(subject, message, recipient_email):
    """
    Sends email via Django core mail functionality.
    """
    from_email = getattr(settings, 'EMAIL_HOST_USER', 'noreply@example.com')
    send_mail(
        subject=subject,
        message=message,
        from_email=from_email,
        recipient_list=[recipient_email],
        fail_silently=False,
    )
