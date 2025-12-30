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
    conn.execute("PRAGMA journal_mode=WAL")  # Non-blocking reads
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

            CREATE TABLE IF NOT EXISTS profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                min_weight_kg REAL,
                max_weight_kg REAL,
                height_cm INTEGER,
                age INTEGER,
                gender TEXT
            );

            CREATE TABLE IF NOT EXISTS measurements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                profile_id INTEGER,
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
                bmi REAL,
                FOREIGN KEY (profile_id) REFERENCES profiles(id)
            );

            CREATE INDEX IF NOT EXISTS idx_measurements_timestamp
            ON measurements(timestamp);

            CREATE INDEX IF NOT EXISTS idx_measurements_profile_id
            ON measurements(profile_id);
        """)
        conn.commit()


def migrate_db() -> None:
    """Run database migrations for existing databases."""
    with get_connection() as conn:
        # Check if profiles table exists
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='profiles'"
        )
        if not cursor.fetchone():
            conn.execute("""
                CREATE TABLE profiles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    min_weight_kg REAL,
                    max_weight_kg REAL,
                    height_cm INTEGER,
                    age INTEGER,
                    gender TEXT
                )
            """)

        # Check for weight columns in profiles (migration from scale_user_id)
        cursor = conn.execute("PRAGMA table_info(profiles)")
        columns = {row[1] for row in cursor.fetchall()}
        if "min_weight_kg" not in columns:
            conn.execute("ALTER TABLE profiles ADD COLUMN min_weight_kg REAL")
        if "max_weight_kg" not in columns:
            conn.execute("ALTER TABLE profiles ADD COLUMN max_weight_kg REAL")

        # Check if profile_id column exists in measurements
        cursor = conn.execute("PRAGMA table_info(measurements)")
        columns = {row[1] for row in cursor.fetchall()}
        if "profile_id" not in columns:
            conn.execute("ALTER TABLE measurements ADD COLUMN profile_id INTEGER")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_measurements_profile_id ON measurements(profile_id)"
            )

        conn.commit()


# Profile CRUD functions
def get_profiles() -> list[dict]:
    """Get all profiles."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM profiles ORDER BY id"
        ).fetchall()
        return [dict(row) for row in rows]


def get_profile(profile_id: int) -> dict | None:
    """Get a single profile by ID."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM profiles WHERE id = ?", (profile_id,)
        ).fetchone()
        return dict(row) if row else None


def save_profile(
    name: str,
    min_weight_kg: float | None = None,
    max_weight_kg: float | None = None,
    height_cm: int | None = None,
    age: int | None = None,
    gender: str | None = None,
    profile_id: int | None = None,
) -> int:
    """Create or update a profile. Returns the profile ID."""
    with get_connection() as conn:
        if profile_id:
            conn.execute(
                """
                UPDATE profiles SET name = ?, min_weight_kg = ?, max_weight_kg = ?,
                    height_cm = ?, age = ?, gender = ?
                WHERE id = ?
                """,
                (name, min_weight_kg, max_weight_kg, height_cm, age, gender, profile_id),
            )
            conn.commit()
            return profile_id
        else:
            cursor = conn.execute(
                """
                INSERT INTO profiles (name, min_weight_kg, max_weight_kg, height_cm, age, gender)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (name, min_weight_kg, max_weight_kg, height_cm, age, gender),
            )
            conn.commit()
            return cursor.lastrowid or 0


def delete_profile(profile_id: int) -> None:
    """Delete a profile."""
    with get_connection() as conn:
        conn.execute("DELETE FROM profiles WHERE id = ?", (profile_id,))
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


def get_latest_measurement(profile_id: int | None = None) -> dict | None:
    """Get the most recent measurement, optionally filtered by profile."""
    with get_connection() as conn:
        if profile_id is not None:
            row = conn.execute(
                """
                SELECT m.*, p.name as profile_name
                FROM measurements m
                LEFT JOIN profiles p ON m.profile_id = p.id
                WHERE m.profile_id = ?
                ORDER BY m.timestamp DESC LIMIT 1
                """,
                (profile_id,),
            ).fetchone()
        else:
            row = conn.execute(
                """
                SELECT m.*, p.name as profile_name
                FROM measurements m
                LEFT JOIN profiles p ON m.profile_id = p.id
                ORDER BY m.timestamp DESC LIMIT 1
                """
            ).fetchone()
        return dict(row) if row else None


def get_measurements(limit: int = 10, profile_id: int | None = None) -> list[dict]:
    """Get recent measurements, newest first, optionally filtered by profile."""
    with get_connection() as conn:
        if profile_id is not None:
            rows = conn.execute(
                """
                SELECT m.*, p.name as profile_name
                FROM measurements m
                LEFT JOIN profiles p ON m.profile_id = p.id
                WHERE m.profile_id = ?
                ORDER BY m.timestamp DESC LIMIT ?
                """,
                (profile_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT m.*, p.name as profile_name
                FROM measurements m
                LEFT JOIN profiles p ON m.profile_id = p.id
                ORDER BY m.timestamp DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]


def get_measurements_since(days: int = 30, profile_id: int | None = None) -> list[dict]:
    """Get measurements from the last N days, oldest first (for charting)."""
    cutoff = datetime.now() - timedelta(days=days)
    with get_connection() as conn:
        if profile_id is not None:
            rows = conn.execute(
                """
                SELECT m.*, p.name as profile_name
                FROM measurements m
                LEFT JOIN profiles p ON m.profile_id = p.id
                WHERE m.timestamp >= ? AND m.profile_id = ?
                ORDER BY m.timestamp ASC
                """,
                (cutoff.isoformat(), profile_id),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT m.*, p.name as profile_name
                FROM measurements m
                LEFT JOIN profiles p ON m.profile_id = p.id
                WHERE m.timestamp >= ?
                ORDER BY m.timestamp ASC
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
