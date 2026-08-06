import pandas as pd
import pickle
import os
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import LabelEncoder
from django.conf import settings


class AnomalyDetector:
    def __init__(self, user_id):
        self.user_id = user_id
        self.model_path = os.path.join(settings.BASE_DIR, 'anomaly_models', f'user_{user_id}_model.pkl')
        self.label_encoders = {
            'city': LabelEncoder(),
            'country': LabelEncoder()
        }
        self.model = None

    def _prepare_data(self, logins):
        # Convert login history to DataFrame
        data = pd.DataFrame(list(logins.values('latitude', 'longitude', 'city', 'country', 'timestamp')))

        # Handle missing values
        data['city'] = data['city'].fillna('Unknown')
        data['country'] = data['country'].fillna('Unknown')

        # Encode categorical features (city, country)
        data['city_encoded'] = self.label_encoders['city'].fit_transform(data['city'])
        data['country_encoded'] = self.label_encoders['country'].fit_transform(data['country'])

        # Extract time-based features
        data['hour'] = data['timestamp'].apply(lambda x: x.hour)
        data['day_of_week'] = data['timestamp'].apply(lambda x: x.weekday())

        # Features for the model
        features = ['latitude', 'longitude', 'city_encoded', 'country_encoded', 'hour', 'day_of_week']
        return data[features]

    def train(self, logins):
        if logins.count() < 4:
            return False  # Not enough data to train

        # Prepare data
        data = self._prepare_data(logins)

        # Train Isolation Forest
        self.model = IsolationForest(contamination=0.1, random_state=42)
        self.model.fit(data)

        # Save the model and label encoders
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        with open(self.model_path, 'wb') as f:
            pickle.dump({
                'model': self.model,
                'label_encoders': self.label_encoders
            }, f)
        return True

    def predict(self, login):
        # Load the model if not already loaded
        if not self.model:
            if not os.path.exists(self.model_path):
                return True  # No model exists, treat as anomaly
            with open(self.model_path, 'rb') as f:
                saved_data = pickle.load(f)
                self.model = saved_data['model']
                self.label_encoders = saved_data['label_encoders']

        # Prepare the current login data
        data = pd.DataFrame({
            'latitude': [login.latitude],
            'longitude': [login.longitude],
            'city': [login.city if login.city else 'Unknown'],
            'country': [login.country if login.country else 'Unknown'],
            'timestamp': [login.timestamp]
        })

        # Encode categorical features
        data['city_encoded'] = self.label_encoders['city'].transform(data['city'])
        data['country_encoded'] = self.label_encoders['country'].transform(data['country'])

        # Extract time-based features
        data['hour'] = data['timestamp'].apply(lambda x: x.hour)
        data['day_of_week'] = data['timestamp'].apply(lambda x: x.weekday())

        # Features for prediction
        features = ['latitude', 'longitude', 'city_encoded', 'country_encoded', 'hour', 'day_of_week']
        prediction = self.model.predict(data[features])
        return prediction[0] == -1  # True if anomaly