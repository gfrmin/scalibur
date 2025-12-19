"""Decode BLE advertisement packets and calculate body composition."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ScaleReading:
    """Decoded scale reading from BLE advertisement."""
    weight_kg: float
    impedance_raw: int
    impedance_ohm: float | None
    user_id: int
    is_complete: bool
    is_locked: bool


@dataclass(frozen=True)
class BodyComposition:
    """Calculated body composition metrics."""
    body_fat_pct: float
    fat_mass_kg: float
    lean_mass_kg: float
    body_water_pct: float
    muscle_mass_kg: float
    bone_mass_kg: float
    bmr_kcal: int
    bmi: float


def decode_packet(manufacturer_id: int, manufacturer_data: bytes) -> ScaleReading | None:
    """Decode tzc scale advertisement packet.

    The scale encodes weight in the BLE manufacturer ID field (unconventional).
    Bleak separates this from the data bytes, so we need both.

    Manufacturer ID: Weight (divide by 600 for kg)

    Data bytes (after manufacturer ID is stripped):
    - Byte 0: Packet type
    - Byte 1: Flags (0x40 = measurement locked)
    - Bytes 2-3: Impedance raw (big-endian), divide by 10 for ohms
    - Bytes 4-5: User ID
    - Byte 6: Status (0x21 = measurement complete)
    - Bytes 7-12: MAC address
    """
    if len(manufacturer_data) < 7:
        return None

    weight_kg = manufacturer_id / 600

    flags = manufacturer_data[1]
    is_locked = flags == 0x40

    impedance_raw = int.from_bytes(manufacturer_data[2:4], "big")
    impedance_ohm = impedance_raw / 10 if impedance_raw > 0 else None

    status = manufacturer_data[6]
    is_complete = status == 0x20

    user_id = int.from_bytes(manufacturer_data[4:6], "big")

    return ScaleReading(
        weight_kg=weight_kg,
        impedance_raw=impedance_raw,
        impedance_ohm=impedance_ohm,
        user_id=user_id,
        is_complete=is_complete,
        is_locked=is_locked,
    )


def calculate_body_composition(
    weight_kg: float,
    impedance_ohm: float,
    height_cm: int,
    age: int,
    gender: str,
) -> BodyComposition:
    """Calculate body composition using standard BIA formulas (openScale compatible)."""
    height_sq = height_cm**2

    # Lean Body Mass
    if gender == "male":
        lbm = 0.485 * (height_sq / impedance_ohm) + 0.338 * weight_kg + 5.32
    else:
        lbm = 0.474 * (height_sq / impedance_ohm) + 0.180 * weight_kg + 5.03

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

    return BodyComposition(
        body_fat_pct=round(body_fat_pct, 1),
        fat_mass_kg=round(fat_mass_kg, 1),
        lean_mass_kg=round(lbm, 1),
        body_water_pct=round(body_water_pct, 1),
        muscle_mass_kg=round(muscle_mass_kg, 1),
        bone_mass_kg=round(bone_mass_kg, 1),
        bmr_kcal=round(bmr),
        bmi=round(bmi, 1),
    )
