from pathlib import Path

# Base directory (where this file lives)
BASE_DIR = Path(__file__).parent

# User profile for body composition calculations
PROFILE = {
    "height_cm": 173,
    "age": 43,
    "gender": "male",
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
