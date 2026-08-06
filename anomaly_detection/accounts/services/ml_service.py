from datetime import datetime
import os
import joblib
import pandas as pd
from django.conf import settings

BASE_DIR = getattr(settings, 'BASE_DIR', os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODEL_PATH = os.path.join(BASE_DIR, 'models', 'anomaly_model.pkl')
if not os.path.exists(MODEL_PATH):
    # Fallback path if models directory is in outer root
    MODEL_PATH = os.path.join(os.path.dirname(BASE_DIR), 'models', 'anomaly_model.pkl')

_anomaly_model = None

def get_anomaly_model():
    """
    Lazy loads the trained Random Forest anomaly model.
    """
    global _anomaly_model
    if _anomaly_model is None:
        if os.path.exists(MODEL_PATH):
            _anomaly_model = joblib.load(MODEL_PATH)
        else:
            print(f"Warning: Model file not found at {MODEL_PATH}")
            return None
    return _anomaly_model


def prepare_anomaly_features(ip_address, latitude, longitude, action, device_type, session_duration=300):
    """
    Prepares input features dataframe for the anomaly detection model.
    """
    first_octet = 0
    if ip_address:
        try:
            first_octet = int(ip_address.split('.')[0])
        except (ValueError, IndexError):
            first_octet = 0

    action_map = {'login': 0, 'upload': 1, 'share': 2, 'download': 3}
    device_map = {'Desktop': 0, 'Mobile': 1, 'Tablet': 2, 'Unknown': 3}

    features = {
        'latitude': latitude,
        'longitude': longitude,
        'hour_of_day': datetime.now().hour,
        'day_of_week': datetime.now().weekday(),
        'ip_first_octet': first_octet,
        'action_encoded': action_map.get(action, 0),
        'device_type_encoded': device_map.get(device_type, 3),
        'session_duration': session_duration
    }
    return pd.DataFrame([features])


def predict_activity_anomaly(ip_address, latitude, longitude, action, device_type, session_duration=300):
    """
    Predicts if a user action is an anomaly (1 = anomaly, 0 = normal).
    """
    model = get_anomaly_model()
    if model is None:
        return 0

    features_df = prepare_anomaly_features(ip_address, latitude, longitude, action, device_type, session_duration)
    try:
        prediction = model.predict(features_df)[0]
        return int(prediction)
    except Exception as e:
        print(f"Error predicting anomaly: {e}")
        return 0
