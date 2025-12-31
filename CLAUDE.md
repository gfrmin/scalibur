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

# Run single test
uv run pytest tests/test_decode.py::TestCalculateBodyComposition::test_male_body_composition -v

# Run manually (two terminals)
uv run python scanner.py    # BLE scanner daemon
uv run python dashboard.py  # Flask web server on :5000

# Deploy to Raspberry Pi
PI_USER=pi ./deploy.sh raspberrypi.local
```

## Architecture

```
BLE Scale (tzc) → scanner.py → raw_packets table
                                    ↓
                               etl.py (on dashboard load)
                                    ↓
                 profiles table → measurements table → dashboard.py → Web UI
                                    ↑
                              decode.py (BIA formulas)
```

**Core modules:**
- `scanner.py` - Async BLE scanning daemon, saves raw packets only
- `etl.py` - Processes raw_packets into measurements, detects profiles by weight range
- `decode.py` - Packet decoding and body composition calculation (BIA formulas)
- `dashboard.py` - Flask app with HTMX partials for profile management
- `db.py` - SQLite abstraction for measurements, raw packets, and profiles
- `config.py` - BLE settings and paths (profile data is in database)

**Multi-user support:** Profiles are matched by weight range (min/max_weight_kg). Body composition is recalculated when profile height/age/gender changes.
