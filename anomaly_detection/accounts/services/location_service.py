import os
import geoip2.database
import requests
from django.conf import settings

BASE_DIR = getattr(settings, 'BASE_DIR', os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def get_ip_address(request):
    """
    Extracts the client's IP address from request headers.
    """
    forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded_for:
        ip_address = forwarded_for.split(',')[0].strip()
    else:
        ip_address = request.META.get('REMOTE_ADDR', '127.0.0.1')
    
    if ip_address.strip() in ['127.0.0.1', '::1']:
        ip_address = '8.8.8.8'  # Development fallback
    return ip_address


def get_location_data(request, ip_address):
    """
    Retrieves location data from browser geolocation or GeoIP2 database fallback.
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
            try:
                response = requests.get(
                    f"https://nominatim.openstreetmap.org/reverse?lat={latitude}&lon={longitude}&format=json",
                    headers={'User-Agent': 'AnomalyDetectionApp/1.0 (your.email@example.com)'},
                    timeout=5
                )
                response.raise_for_status()
                data = response.json()
                address = data.get('address', {})
                city = address.get('city') or address.get('town') or address.get('village')
                country = address.get('country')
                location_retrieved = True
            except Exception as e:
                print(f"Reverse Geocoding Error: {e}")
        except ValueError:
            latitude = 0.0
            longitude = 0.0
    else:
        try:
            db_path = os.path.join(BASE_DIR, 'GeoLite2-City.mmdb')
            if not os.path.exists(db_path):
                db_path = os.path.join(BASE_DIR, 'anomaly_detection', 'GeoLite2-City.mmdb')

            reader = geoip2.database.Reader(db_path)
            response = reader.city(ip_address)
            latitude = response.location.latitude
            longitude = response.location.longitude
            city = response.city.name
            country = response.country.name
            reader.close()
            location_retrieved = True
        except geoip2.errors.AddressNotFoundError as e:
            print(f"GeoIP2 Error: Address not found - {e}")
        except Exception as e:
            print(f"GeoIP2 Error: {e}")

    return latitude, longitude, city, country, location_retrieved


def get_device_type(request):
    """
    Determines device type from HTTP User Agent.
    """
    user_agent = request.META.get('HTTP_USER_AGENT', 'Unknown')
    if 'Mobile' in user_agent:
        return 'Mobile'
    elif 'Tablet' in user_agent:
        return 'Tablet'
    return 'Desktop'
