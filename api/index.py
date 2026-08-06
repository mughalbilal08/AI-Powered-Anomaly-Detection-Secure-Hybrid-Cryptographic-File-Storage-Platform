import os
import sys

# Add anomaly_detection subfolder to path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(BASE_DIR, 'anomaly_detection'))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'anomaly_detection.settings')

from django.core.wsgi import get_wsgi_application
app = get_wsgi_application()
