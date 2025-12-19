# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Scalibur is a BLE body composition scale monitor for Raspberry Pi. It reads weight and impedance data from a GoodPharm TY5108 scale (BLE name "tzc") and displays measurements on a web dashboard with body composition calculations using standard BIA formulas.

## Commands

```bash
# Install dependencies
uv sync

# Run tests
uv run pytest

# Run manually (two terminals)
uv run python scanner.py    # BLE scanner daemon
uv run python dashboard.py  # Flask web server on :5000

# Deploy to Raspberry Pi
PI_USER=pi ./deploy.sh raspberrypi.local
```

## Architecture

```
BLE Scale (tzc) → scanner.py → measurements.db → dashboard.py → Web UI
                     ↓
                 decode.py (packet decoding + body composition)
```

**Core modules:**
- `scanner.py` - Async BLE scanning daemon with 30s measurement debounce
- `decode.py` - Packet decoding and body composition calculation (BIA formulas)
- `dashboard.py` - Flask app serving web UI and chart data API
- `db.py` - SQLite abstraction for measurements and raw packets
- `config.py` - User profile (height, age, gender), BLE settings
