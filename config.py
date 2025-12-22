from pathlib import Path

# Base directory (where this file lives)
BASE_DIR = Path(__file__).parent

# User profile for body composition calculations
PROFILE = {
    "height_cm": 170,
    "age": 30,
    "gender": "male",
}

# BLE settings
SCALE_NAME = "tzc"
MANUFACTURER_ID = 0x88C0

# Database (stored alongside code)
DATABASE_PATH = BASE_DIR / "measurements.db"

# Dashboard
DASHBOARD_HOST = "0.0.0.0"
DASHBOARD_PORT = 5000
