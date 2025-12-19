from pathlib import Path

# Base directory (where this file lives)
BASE_DIR = Path(__file__).parent

# User profile for body composition calculations
# Copy this file to config.py and update with your values
PROFILE = {
    "height_cm": 170,  # Your height in centimeters
    "age": 30,         # Your age in years
    "gender": "male",  # "male" or "female"
}

# BLE settings
SCALE_NAME = "tzc"
MANUFACTURER_ID = 0xA6C0

# Measurement settings
MEASUREMENT_COOLDOWN_SECONDS = 30

# Database (stored alongside code)
DATABASE_PATH = BASE_DIR / "measurements.db"

# Dashboard
DASHBOARD_HOST = "0.0.0.0"
DASHBOARD_PORT = 5000
