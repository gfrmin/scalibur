"""ETL: Process raw_packets into measurements."""

import sqlite3
from datetime import datetime, timedelta
from config import DATABASE_PATH
from decode import calculate_body_composition, decode_packet
import db


def get_all_packets(conn: sqlite3.Connection) -> list[dict]:
    """Get all raw packets ordered by timestamp."""
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id, timestamp, packet_hex FROM raw_packets ORDER BY timestamp"
    ).fetchall()
    return [dict(row) for row in rows]


def parse_packet_hex(packet_hex: str) -> tuple[int, bytes] | None:
    """Parse 'mfgid:data' format into (manufacturer_id, data_bytes)."""
    try:
        mfg_id_hex, data_hex = packet_hex.split(":")
        return int(mfg_id_hex, 16), bytes.fromhex(data_hex)
    except (ValueError, AttributeError):
        return None


def group_into_sessions(packets: list[dict], gap_seconds: int = 30) -> list[list[dict]]:
    """Group packets into sessions based on time gaps."""
    if not packets:
        return []

    sessions = []
    current_session = [packets[0]]

    for packet in packets[1:]:
        prev_time = datetime.fromisoformat(current_session[-1]["timestamp"])
        curr_time = datetime.fromisoformat(packet["timestamp"])

        if curr_time - prev_time > timedelta(seconds=gap_seconds):
            # Gap too large - start new session
            sessions.append(current_session)
            current_session = [packet]
        else:
            current_session.append(packet)

    sessions.append(current_session)
    return sessions


def find_best_reading(session: list[dict]) -> dict | None:
    """Find the best reading from a session (last 0x21 packet, or last 0x20 if no 0x21)."""
    best = None
    best_status = 0

    for packet in session:
        parsed = parse_packet_hex(packet["packet_hex"])
        if not parsed:
            continue

        mfg_id, data = parsed
        reading = decode_packet(mfg_id, data)
        if reading is None:
            continue

        # Extract status byte (byte 6)
        status = data[6] if len(data) > 6 else 0

        # Prefer 0x21 (complete with impedance) over 0x20
        if status == 0x21:
            best = {"packet": packet, "reading": reading, "status": status}
            best_status = 0x21
        elif status == 0x20 and best_status != 0x21:
            best = {"packet": packet, "reading": reading, "status": status}
            best_status = 0x20

    return best


def detect_profile(scale_user_id: int, profiles: list[dict]) -> dict | None:
    """Find profile matching the scale's user_id bytes.

    Args:
        scale_user_id: The user_id from bytes 4-5 of the BLE packet
        profiles: List of profile dicts from database

    Returns:
        Matching profile dict, or None if no match
    """
    for profile in profiles:
        if profile.get("scale_user_id") == scale_user_id:
            return profile
    return None


def find_existing_measurement(
    conn: sqlite3.Connection, timestamp: str, window_seconds: int = 30
) -> dict | None:
    """Find existing measurement within window_seconds of timestamp."""
    row = conn.execute(
        """
        SELECT id, timestamp, impedance_ohm
        FROM measurements
        WHERE ABS(strftime('%s', timestamp) - strftime('%s', ?)) < ?
        ORDER BY ABS(strftime('%s', timestamp) - strftime('%s', ?))
        LIMIT 1
        """,
        (timestamp, window_seconds, timestamp),
    ).fetchone()
    if row:
        return {"id": row[0], "timestamp": row[1], "impedance_ohm": row[2]}
    return None


def update_measurement(
    conn: sqlite3.Connection,
    measurement_id: int,
    reading,
    composition,
    profile_id: int | None = None,
) -> None:
    """Update an existing measurement with new data."""
    conn.execute(
        """
        UPDATE measurements SET
            profile_id = ?, weight_kg = ?, impedance_raw = ?, impedance_ohm = ?,
            body_fat_pct = ?, fat_mass_kg = ?, lean_mass_kg = ?, body_water_pct = ?,
            muscle_mass_kg = ?, bone_mass_kg = ?, bmr_kcal = ?, bmi = ?
        WHERE id = ?
        """,
        (
            profile_id,
            reading.weight_kg,
            reading.impedance_raw if reading.impedance_raw else None,
            reading.impedance_ohm,
            composition.body_fat_pct if composition else None,
            composition.fat_mass_kg if composition else None,
            composition.lean_mass_kg if composition else None,
            composition.body_water_pct if composition else None,
            composition.muscle_mass_kg if composition else None,
            composition.bone_mass_kg if composition else None,
            composition.bmr_kcal if composition else None,
            composition.bmi if composition else None,
            measurement_id,
        ),
    )


def save_measurement(
    conn: sqlite3.Connection,
    timestamp: str,
    reading,
    composition,
    profile_id: int | None = None,
) -> int:
    """Save measurement to database."""
    cursor = conn.execute(
        """
        INSERT INTO measurements (
            timestamp, profile_id, weight_kg, impedance_raw, impedance_ohm,
            body_fat_pct, fat_mass_kg, lean_mass_kg, body_water_pct,
            muscle_mass_kg, bone_mass_kg, bmr_kcal, bmi
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            timestamp,
            profile_id,
            reading.weight_kg,
            reading.impedance_raw if reading.impedance_raw else None,
            reading.impedance_ohm,
            composition.body_fat_pct if composition else None,
            composition.fat_mass_kg if composition else None,
            composition.lean_mass_kg if composition else None,
            composition.body_water_pct if composition else None,
            composition.muscle_mass_kg if composition else None,
            composition.bone_mass_kg if composition else None,
            composition.bmr_kcal if composition else None,
            composition.bmi if composition else None,
        ),
    )
    return cursor.lastrowid or 0


def run_etl() -> dict:
    """Run the ETL process. Returns stats."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.execute("PRAGMA journal_mode=WAL")

    # Load profiles from database
    profiles = db.get_profiles()

    try:
        packets = get_all_packets(conn)

        if not packets:
            return {"packets": 0, "sessions": 0, "measurements": 0, "updated": 0}

        sessions = group_into_sessions(packets)
        measurements_created = 0
        measurements_updated = 0

        for session in sessions:
            best = find_best_reading(session)
            if not best:
                continue

            reading = best["reading"]
            timestamp = best["packet"]["timestamp"]

            # Detect profile from packet's user_id
            profile = detect_profile(reading.user_id, profiles)
            profile_id = profile["id"] if profile else None

            # Calculate body composition if we have impedance AND a profile
            composition = None
            if reading.impedance_ohm and profile:
                composition = calculate_body_composition(
                    weight_kg=reading.weight_kg,
                    impedance_ohm=reading.impedance_ohm,
                    height_cm=profile["height_cm"],
                    age=profile["age"],
                    gender=profile["gender"],
                )

            # Check for existing measurement in time window
            existing = find_existing_measurement(conn, timestamp)
            if existing:
                # Update if new reading has impedance but existing doesn't
                if reading.impedance_ohm and not existing["impedance_ohm"]:
                    update_measurement(conn, existing["id"], reading, composition, profile_id)
                    measurements_updated += 1
                # Otherwise skip (already have this measurement)
            else:
                save_measurement(conn, timestamp, reading, composition, profile_id)
                measurements_created += 1

        conn.commit()
        return {
            "packets": len(packets),
            "sessions": len(sessions),
            "measurements": measurements_created,
            "updated": measurements_updated,
        }
    finally:
        conn.close()


if __name__ == "__main__":
    stats = run_etl()
    print(f"Processed {stats['packets']} packets")
    print(f"Found {stats['sessions']} sessions")
    print(f"Created {stats['measurements']} measurements")
    print(f"Updated {stats['updated']} measurements")
