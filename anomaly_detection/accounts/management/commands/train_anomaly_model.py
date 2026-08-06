import os
import joblib
import pandas as pd
from django.core.management.base import BaseCommand
from django.conf import settings
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split

class Command(BaseCommand):
    help = 'Train Random Forest anomaly detection model using activity data.'

    def add_arguments(self, parser):
        parser.add_argument('--csv', type=str, default='data/user_activity_data.csv', help='Path to CSV dataset.')

    def handle(self, *args, **options):
        csv_path = options['csv']

        if not os.path.exists(csv_path):
            base_dir = getattr(settings, 'BASE_DIR', '')
            csv_path = os.path.join(base_dir, options['csv'])
            if not os.path.exists(csv_path):
                csv_path = os.path.join(os.path.dirname(base_dir), options['csv'])

        if not os.path.exists(csv_path):
            self.stderr.write(self.style.ERROR(f"Dataset CSV not found at '{csv_path}'"))
            return

        self.stdout.write(f"Loading activity dataset from '{csv_path}'...")
        df = pd.read_csv(csv_path)

        features = ['latitude', 'longitude', 'hour_of_day', 'day_of_week', 'ip_first_octet', 'action_encoded', 'device_type_encoded', 'session_duration']
        X = df[features]
        y = df['is_anomaly']

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

        model = RandomForestClassifier(n_estimators=100, random_state=42, class_weight='balanced')
        model.fit(X_train, y_train)

        y_pred = model.predict(X_test)
        self.stdout.write(self.style.SUCCESS("Model Performance Evaluation:"))
        self.stdout.write(classification_report(y_test, y_pred))

        base_dir = getattr(settings, 'BASE_DIR', '')
        models_dir = os.path.join(base_dir, 'models')
        os.makedirs(models_dir, exist_ok=True)
        model_file = os.path.join(models_dir, 'anomaly_model.pkl')

        joblib.dump(model, model_file)
        self.stdout.write(self.style.SUCCESS(f"Trained model saved successfully to '{model_file}'"))
