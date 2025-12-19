# GoodPharm/tzc Scale Monitor

## Protocol Spec

**Device:** GoodPharm TY5108 body composition scale  
**BLE Name:** `tzc`  
**Service UUID:** `0xFFFE`  
**Manufacturer ID:** `0xA6C0`  

### Advertisement Packet Format (14 bytes)

| Bytes | Example | Description |
|-------|---------|-------------|
| 0-1 | `C0C8` | Weight (big-endian), divide by 600 for kg |
| 2 | `03` | Packet type |
| 3 | `3E`/`40` | Flags (0x40 = measurement locked) |
| 4-5 | `1399` | Impedance raw (big-endian), divide by 10 for ohms |
| 6-7 | `0002` | User ID |
| 8 | `20`/`21` | Status (0x21 = measurement complete) |
| 9-14 | `FE98...` | MAC address |

### Decoding Logic

```python
def decode_packet(manufacturer_data: bytes) -> dict:
    """Decode tzc scale advertisement packet."""
    if len(manufacturer_data) < 9:
        return None
    
    weight_raw = int.from_bytes(manufacturer_data[0:2], 'big')
    weight_kg = weight_raw / 600
    
    flags = manufacturer_data[3]
    is_locked = (flags == 0x40)
    
    impedance_raw = int.from_bytes(manufacturer_data[4:6], 'big')
    impedance_ohm = impedance_raw / 10 if impedance_raw > 0 else None
    
    status = manufacturer_data[8]
    is_complete = (status == 0x21)
    
    user_id = int.from_bytes(manufacturer_data[6:8], 'big')
    
    return {
        "weight_kg": weight_kg,
        "impedance_raw": impedance_raw,
        "impedance_ohm": impedance_ohm,
        "user_id": user_id,
        "is_complete": is_complete,
        "is_locked": is_locked,
    }
```

### Body Composition Formulas

```python
def calculate_body_composition(
    weight_kg: float,
    impedance_ohm: float,
    height_cm: int,
    age: int,
    gender: str  # "male" or "female"
) -> dict:
    """Standard BIA formulas (same as openScale)."""
    
    height_sq = height_cm ** 2
    
    # Lean Body Mass
    if gender == "male":
        lbm = (0.485 * (height_sq / impedance_ohm) 
               + 0.338 * weight_kg + 5.32)
    else:
        lbm = (0.474 * (height_sq / impedance_ohm) 
               + 0.180 * weight_kg + 5.03)
    
    # Body Fat
    fat_mass_kg = weight_kg - lbm
    body_fat_pct = (fat_mass_kg / weight_kg) * 100
    
    # Body Water (approximately 73% of lean mass)
    body_water_kg = lbm * 0.73
    body_water_pct = (body_water_kg / weight_kg) * 100
    
    # Muscle Mass (approximately 90% of lean mass)
    muscle_mass_kg = lbm * 0.9
    
    # Bone Mass (estimate based on weight and gender)
    if gender == "male":
        bone_mass_kg = 0.18 * (height_cm / 100) ** 2 * 22
    else:
        bone_mass_kg = 0.18 * (height_cm / 100) ** 2 * 20
    bone_mass_kg = min(bone_mass_kg, lbm * 0.05)  # Cap at 5% of LBM
    
    # BMR (Mifflin-St Jeor)
    if gender == "male":
        bmr = 88.36 + (13.4 * weight_kg) + (4.8 * height_cm) - (5.7 * age)
    else:
        bmr = 447.6 + (9.2 * weight_kg) + (3.1 * height_cm) - (4.3 * age)
    
    # BMI
    bmi = weight_kg / (height_cm / 100) ** 2
    
    return {
        "body_fat_pct": round(body_fat_pct, 1),
        "fat_mass_kg": round(fat_mass_kg, 1),
        "lean_mass_kg": round(lbm, 1),
        "body_water_pct": round(body_water_pct, 1),
        "muscle_mass_kg": round(muscle_mass_kg, 1),
        "bone_mass_kg": round(bone_mass_kg, 1),
        "bmr_kcal": round(bmr),
        "bmi": round(bmi, 1),
    }
```

---

## Architecture

```
scanner.py (systemd daemon)
    │
    │ BLE advertisement
    │ └─ filter by name="tzc"
    │ └─ wait for is_complete=True
    │ └─ debounce (30s cooldown)
    │
    ▼
measurements.db (SQLite)
    │
    │ Tables:
    │ └─ raw_packets (timestamp, packet_hex)
    │ └─ measurements (timestamp, weight, impedance, fat%, etc.)
    │
    ▼
dashboard.py (Flask on :5000)
    │
    └─ GET / → latest reading + weight chart + history table
```

---

## Database Schema

```sql
CREATE TABLE raw_packets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    packet_hex TEXT NOT NULL
);

CREATE TABLE measurements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    weight_kg REAL NOT NULL,
    impedance_raw INTEGER,
    impedance_ohm REAL,
    body_fat_pct REAL,
    fat_mass_kg REAL,
    lean_mass_kg REAL,
    body_water_pct REAL,
    muscle_mass_kg REAL,
    bone_mass_kg REAL,
    bmr_kcal INTEGER,
    bmi REAL
);
```

---

## User Profile Config

```python
# config.py
PROFILE = {
    "height_cm": 173,
    "age": 43,
    "gender": "male",
}

SCALE_NAME = "tzc"
MEASUREMENT_COOLDOWN_SECONDS = 30
```

---

## Dependencies

```
# requirements.txt
bleak>=0.21.0
flask>=3.0.0
```

---

## Systemd Units

### /etc/systemd/system/scale-scanner.service
```ini
[Unit]
Description=BLE Scale Scanner
After=bluetooth.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/scale-monitor
ExecStart=/home/pi/scale-monitor/venv/bin/python scanner.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### /etc/systemd/system/scale-dashboard.service
```ini
[Unit]
Description=Scale Dashboard
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/scale-monitor
ExecStart=/home/pi/scale-monitor/venv/bin/python dashboard.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

---

## MVP Dashboard

Single page showing:
1. **Latest reading** - big number for weight, smaller for body fat%
2. **Line chart** - weight over last 30 days (Chart.js)
3. **Table** - last 10 measurements

---

## Future Ideas

- [ ] openScale PR (add "tzc" to BluetoothFactory.java)
- [ ] Multi-user support (use user_id from packet)
- [ ] Goal tracking
- [ ] CSV export
- [ ] Apple Health / Google Fit sync
