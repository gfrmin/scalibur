#!/usr/bin/env bash
# Deploy scalibur to Raspberry Pi
# Usage: ./deploy.sh [pi-hostname]
#
# Environment variables:
#   PI_USER - Username on the Pi (default: pi)
#   PI_DIR  - Installation directory (default: /home/$PI_USER/scalibur)

set -euo pipefail

PI_HOST="${1:-raspberrypi.local}"
PI_USER="${PI_USER:-pi}"
PI_DIR="${PI_DIR:-/home/${PI_USER}/scalibur}"

echo "Deploying to ${PI_USER}@${PI_HOST}:${PI_DIR}"

# Sync code (exclude dev files)
rsync -avz --delete \
    --exclude '.venv/' \
    --exclude '__pycache__/' \
    --exclude '*.pyc' \
    --exclude '.git/' \
    --exclude 'measurements.db' \
    --exclude '.pytest_cache/' \
    ./ "${PI_USER}@${PI_HOST}:${PI_DIR}/"

# Install/update on Pi
ssh "${PI_USER}@${PI_HOST}" << 'EOF'
cd ~/scalibur

# Install uv if not present
if ! command -v uv &> /dev/null; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
    source ~/.local/bin/env
fi

# Sync dependencies
uv sync --no-dev

# Install systemd units if not already installed
# Note: You must edit the service files first to replace YOUR_USER with your username
if [ ! -f /etc/systemd/system/scalibur-scanner.service ]; then
    echo "Installing systemd services..."
    echo "Make sure you've replaced YOUR_USER in the service files!"
    sudo cp systemd/scalibur-scanner.service /etc/systemd/system/
    sudo cp systemd/scalibur-dashboard.service /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl enable scalibur-scanner scalibur-dashboard
fi

# Restart services
sudo systemctl restart scalibur-scanner scalibur-dashboard

echo "Deployed. Services status:"
sudo systemctl status scalibur-scanner scalibur-dashboard --no-pager || true
EOF
