"""BLE scanner daemon for tzc scale."""

import asyncio
import logging
from datetime import datetime, timedelta

from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

import db
from config import (
    MANUFACTURER_ID,
    MEASUREMENT_COOLDOWN_SECONDS,
    PROFILE,
    SCALE_NAME,
)
from decode import calculate_body_composition, decode_packet

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)


class ScaleScanner:
    """BLE scanner that detects and records scale measurements."""

    def __init__(self) -> None:
        self.last_measurement_time: datetime | None = None

    def is_within_cooldown(self) -> bool:
        """Check if we're still within the debounce cooldown period."""
        if self.last_measurement_time is None:
            return False
        cooldown = timedelta(seconds=MEASUREMENT_COOLDOWN_SECONDS)
        return datetime.now() - self.last_measurement_time < cooldown

    def handle_detection(
        self,
        device: BLEDevice,
        advertisement_data: AdvertisementData,
    ) -> None:
        """Handle BLE advertisement detection."""
        # Filter by device name
        if device.name != SCALE_NAME:
            return

        # Check for manufacturer data with our ID
        if MANUFACTURER_ID not in advertisement_data.manufacturer_data:
            return

        manufacturer_data = advertisement_data.manufacturer_data[MANUFACTURER_ID]

        # Decode the packet
        reading = decode_packet(manufacturer_data)
        if reading is None:
            log.warning("Failed to decode packet: %s", manufacturer_data.hex())
            return

        # Only process complete measurements
        if not reading.is_complete:
            log.debug(
                "Incomplete reading: %.1f kg (waiting for stable)",
                reading.weight_kg,
            )
            return

        # Debounce
        if self.is_within_cooldown():
            log.debug("Within cooldown period, skipping")
            return

        log.info(
            "Complete measurement: %.1f kg, impedance: %s ohms",
            reading.weight_kg,
            reading.impedance_ohm,
        )

        # Save raw packet
        db.save_raw_packet(manufacturer_data.hex())

        # Calculate body composition if we have impedance
        if reading.impedance_ohm is not None:
            composition = calculate_body_composition(
                weight_kg=reading.weight_kg,
                impedance_ohm=reading.impedance_ohm,
                height_cm=PROFILE["height_cm"],
                age=PROFILE["age"],
                gender=PROFILE["gender"],
            )
            db.save_measurement(
                weight_kg=reading.weight_kg,
                impedance_raw=reading.impedance_raw,
                impedance_ohm=reading.impedance_ohm,
                body_fat_pct=composition.body_fat_pct,
                fat_mass_kg=composition.fat_mass_kg,
                lean_mass_kg=composition.lean_mass_kg,
                body_water_pct=composition.body_water_pct,
                muscle_mass_kg=composition.muscle_mass_kg,
                bone_mass_kg=composition.bone_mass_kg,
                bmr_kcal=composition.bmr_kcal,
                bmi=composition.bmi,
            )
            log.info(
                "Saved with body composition: %.1f%% fat, BMI %.1f",
                composition.body_fat_pct,
                composition.bmi,
            )
        else:
            # Weight only (no impedance)
            db.save_measurement(weight_kg=reading.weight_kg)
            log.info("Saved weight only (no impedance)")

        self.last_measurement_time = datetime.now()


async def main() -> None:
    """Run the BLE scanner."""
    log.info("Initializing database...")
    db.init_db()

    # Load last measurement time from DB for cooldown
    scanner = ScaleScanner()
    scanner.last_measurement_time = db.get_last_measurement_time()

    log.info("Starting BLE scanner for '%s' scale...", SCALE_NAME)

    async with BleakScanner(detection_callback=scanner.handle_detection):
        # Run forever
        while True:
            await asyncio.sleep(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Scanner stopped")
