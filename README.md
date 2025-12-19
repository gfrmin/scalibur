# Scalibur

BLE body composition scale monitor for Raspberry Pi. Reads weight and impedance data from a GoodPharm TY5108 (BLE name "tzc") scale and displays it on a web dashboard.

## Features

- Continuous BLE scanning for scale advertisements
- Body composition calculation using standard BIA formulas (body fat %, muscle mass, BMR, etc.)
- SQLite database for persistent storage
- Web dashboard with weight charts and measurement history

## Requirements

- Raspberry Pi (or any Linux system with Bluetooth LE)
- Python 3.11+
- [uv](https://github.com/astral-sh/uv) package manager
- GoodPharm TY5108 body composition scale (BLE name: "tzc")

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/scalibur.git
cd scalibur
```

### 2. Install dependencies

```bash
uv sync
```

### 3. Configure your profile

Copy the example config and edit with your details:

```bash
cp config.example.py config.py
```

Edit `config.py` with your height, age, and gender for accurate body composition calculations.

### 4. Run manually (for testing)

```bash
# Terminal 1: Start the BLE scanner
uv run python scanner.py

# Terminal 2: Start the dashboard
uv run python dashboard.py
```

The dashboard will be available at `http://localhost:5000`

## Raspberry Pi Deployment

### 1. Deploy to your Pi

```bash
# Set your Pi's hostname and username
PI_USER=pi ./deploy.sh raspberrypi.local
```

### 2. Configure systemd services

Before the first deployment, edit the service files to replace `YOUR_USER` with your Pi username:

```bash
# In systemd/scalibur-scanner.service and scalibur-dashboard.service
# Replace YOUR_USER with your actual username (e.g., pi)
```

The deploy script will install and enable the systemd services on first run.

### 3. Access the dashboard

Open `http://raspberrypi.local:5000` in your browser.

## Usage

1. Stand on the scale and wait for the measurement to complete
2. The scanner detects the BLE advertisement and stores the reading
3. View your data on the web dashboard

## Architecture

```
scanner.py (systemd daemon)
    │
    │ BLE advertisement
    │ └─ filter by name="tzc"
    │ └─ wait for measurement complete
    │ └─ debounce (30s cooldown)
    │
    ▼
measurements.db (SQLite)
    │
    ▼
dashboard.py (Flask on :5000)
    │
    └─ Latest reading + weight chart + history
```

## Security Notes

- The web dashboard has no authentication and listens on all interfaces by default
- Only expose on trusted networks or add a reverse proxy with authentication
- The database contains personal health data - keep backups secure

## Protocol

See [SPEC.md](SPEC.md) for the BLE packet format and body composition formulas.

## License

GPL-3.0 - see [LICENSE](LICENSE)
