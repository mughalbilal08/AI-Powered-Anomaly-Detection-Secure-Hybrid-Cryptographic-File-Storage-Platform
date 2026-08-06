import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
import joblib
import os

# Load dataset
df = pd.read_csv('data/user_activity_data.csv')

# Features and labels
features = ['latitude', 'longitude', 'hour_of_day', 'day_of_week', 'ip_first_octet', 'action_encoded', 'device_type_encoded', 'session_duration']
X = df[features]
y = df['is_anomaly']

# Split data
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Train Random Forest Classifier
model = RandomForestClassifier(n_estimators=100, random_state=42, class_weight='balanced')
model.fit(X_train, y_train)

# Evaluate model
y_pred = model.predict(X_test)
print("Model Performance:")
print(classification_report(y_test, y_pred))

# Create models/ directory if it doesn't exist
if not os.path.exists('models'):
    os.makedirs('models')

# Save the model
joblib.dump(model, 'models/anomaly_model.pkl')
print("Model saved as 'models/anomaly_model.pkl'")