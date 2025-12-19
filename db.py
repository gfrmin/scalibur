"""SQLite database for scale measurements."""

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Iterator

from config import DATABASE_PATH


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    """Context manager for database connections."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db() -> None:
    """Initialize database with schema."""
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS raw_packets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                packet_hex TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS measurements (
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

            CREATE INDEX IF NOT EXISTS idx_measurements_timestamp
            ON measurements(timestamp);
        """)
        conn.commit()


def save_raw_packet(packet_hex: str) -> int:
    """Save raw packet data and return the row ID."""
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO raw_packets (packet_hex) VALUES (?)",
            (packet_hex,),
        )
        conn.commit()
        return cursor.lastrowid or 0


def save_measurement(
    weight_kg: float,
    impedance_raw: int | None = None,
    impedance_ohm: float | None = None,
    body_fat_pct: float | None = None,
    fat_mass_kg: float | None = None,
    lean_mass_kg: float | None = None,
    body_water_pct: float | None = None,
    muscle_mass_kg: float | None = None,
    bone_mass_kg: float | None = None,
    bmr_kcal: int | None = None,
    bmi: float | None = None,
) -> int:
    """Save a measurement and return the row ID."""
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO measurements (
                weight_kg, impedance_raw, impedance_ohm, body_fat_pct,
                fat_mass_kg, lean_mass_kg, body_water_pct, muscle_mass_kg,
                bone_mass_kg, bmr_kcal, bmi
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                weight_kg,
                impedance_raw,
                impedance_ohm,
                body_fat_pct,
                fat_mass_kg,
                lean_mass_kg,
                body_water_pct,
                muscle_mass_kg,
                bone_mass_kg,
                bmr_kcal,
                bmi,
            ),
        )
        conn.commit()
        return cursor.lastrowid or 0


def get_latest_measurement() -> dict | None:
    """Get the most recent measurement."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM measurements ORDER BY timestamp DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None


def get_measurements(limit: int = 10) -> list[dict]:
    """Get recent measurements, newest first."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM measurements ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]


def get_measurements_since(days: int = 30) -> list[dict]:
    """Get measurements from the last N days, oldest first (for charting)."""
    cutoff = datetime.now() - timedelta(days=days)
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM measurements
            WHERE timestamp >= ?
            ORDER BY timestamp ASC
            """,
            (cutoff.isoformat(),),
        ).fetchall()
        return [dict(row) for row in rows]


def get_last_measurement_time() -> datetime | None:
    """Get timestamp of the most recent measurement (for debouncing)."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT timestamp FROM measurements ORDER BY timestamp DESC LIMIT 1"
        ).fetchone()
        if row:
            return datetime.fromisoformat(row["timestamp"])
        return None
