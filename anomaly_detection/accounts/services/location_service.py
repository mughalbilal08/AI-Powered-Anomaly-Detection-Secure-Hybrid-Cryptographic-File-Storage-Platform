import os
import geoip2.webservice
import geoip2.errors
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
    Retrieves location data: lat/lon from browser (if available), 
    city/country always from MaxMind GeoIP2 lookup.
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
        except ValueError:
            latitude = 0.0
            longitude = 0.0

    # Hamesha MaxMind se city/country lein (chahe lat/lon mil bhi jaye)
    try:
        client = geoip2.webservice.Client(
            settings.MAXMIND_ACCOUNT_ID,
            settings.MAXMIND_LICENSE_KEY,
            host='geolite.info'
        )
        response = client.city(ip_address)
        city = response.city.name
        country = response.country.name
        if latitude == 0.0 and longitude == 0.0:
            latitude = response.location.latitude
            longitude = response.location.longitude
        client.close()
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
