import os
import re
import requests
import geoip2.database
from django.contrib.auth import authenticate
from django.conf import settings
from datetime import datetime
from django.core.mail import send_mail

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def get_ip_address(request):

    forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded_for:
        ip_address = forwarded_for.split(',')[0].strip()
    else:
        ip_address = request.META.get('REMOTE_ADDR', '127.0.0.1')
    if ip_address.strip() in ['127.0.0.1', '::1']:
        ip_address = '8.8.8.8'  # Use a test IP for local development
    print(f"IP Address: {ip_address}")
    return ip_address

def get_location_data(request, ip_address):
    """
    Retrieve location data either from browser geolocation or GeoIP2 database.
    Returns (latitude, longitude, city, country, location_retrieved).
    """
    latitude = 0.0
    longitude = 0.0
    city = None
    country = None
    location_retrieved = False

    latitude_input = request.POST.get('latitude')
    longitude_input = request.POST.get('longitude')

    if latitude_input and longitude_input:
        try:
            latitude = float(latitude_input)
            longitude = float(longitude_input)
            print(f"Browser Geolocation - Latitude: {latitude}, longitude: {longitude}")
            try:
                response = requests.get(
                    f"https://nominatim.openstreetmap.org/reverse?lat={latitude}&lon={longitude}&format=json",
                    headers={'User-Agent': 'AnomalyDetectionApp/1.0 (your.email@example.com)'}
                )
                response.raise_for_status()
                data = response.json()
                city = data.get('address', {}).get('city') or data.get('address', {}).get('town') or data.get('address', {}).get('village')
                country = data.get('address', {}).get('country')
                print(f"Browser Geolocation - City: {city}, Country: {country}")
                location_retrieved = True
            except Exception as e:
                print(f"Reverse Geocoding Error: {e}")
        except ValueError:
            latitude = 0.0
            longitude = 0.0
    else:
        try:
            reader = geoip2.database.Reader(os.path.join(BASE_DIR, 'anomaly_detection', 'GeoLite2-City.mmdb'))
            response = reader.city(ip_address)
            latitude = response.location.latitude
            longitude = response.location.longitude
            city = response.city.name
            country = response.country.name
            print(f"GeoLite2 - Latitude: {latitude}, longitude: {longitude}, City: {city}, Country: {country}")
            reader.close()
            location_retrieved = True
        except geoip2.errors.AddressNotFoundError as e:
            print(f"GeoIP2 Error: Address not found - {e}")
        except Exception as e:
            print(f"GeoIP2 Error: {e}")

    return latitude, longitude, city, country, location_retrieved

def get_device_type(request):
    """
    Determine the device type from the user agent.
    """
    device_type = request.META.get('HTTP_USER_AGENT', 'Unknown')
    if 'Mobile' in device_type:
        device_type = 'Mobile'
    elif 'Tablet' in device_type:
        device_type = 'Tablet'
    else:
        device_type = 'Desktop'
    return device_type

def prepare_anomaly_features(ip_address, latitude, longitude, action, device_type, session_duration):
    """
    Prepare features for anomaly detection model.
    """
    features = {
        'latitude': latitude,
        'longitude': longitude,
        'hour_of_day': datetime.now().hour,
        'day_of_week': datetime.now().weekday(),
        'ip_first_octet': int(ip_address.split('.')[0]) if ip_address else 0,
        'action_encoded': {'login': 0, 'upload': 1, 'share': 2, 'download': 3}.get(action, 0),
        'device_type_encoded': {'Desktop': 0, 'Mobile': 1, 'Tablet': 2, 'Unknown': 3}.get(device_type, 3),
        'session_duration': session_duration
    }
    return features

def validate_password(password):
    """
    Validate password based on specified criteria.
    Returns an error message if validation fails, else None.
    """
    if len(password) < 8:
        return 'Password must be at least 8 characters long.'
    if not re.search(r'[A-Z]', password):
        return 'Password must contain at least one uppercase letter.'
    if not re.search(r'[a-z]', password):
        return 'Password must contain at least one lowercase letter.'
    if not re.search(r'[0-9]', password):
        return 'Password must contain at least one number.'
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return 'Password must contain at least one special character (e.g., !@#$%^&*).'
    return None

def send_email(subject, message, recipient):
    """
    Send an email to the specified recipient.
    """
    send_mail(
        subject,
        message,
        settings.EMAIL_HOST_USER,
        [recipient],
        fail_silently=False,
    )

def authenticate_user(request, username, password):
    """
    Authenticate a user with the given username and password.
    """
    return authenticate(request, username=username, password=password)