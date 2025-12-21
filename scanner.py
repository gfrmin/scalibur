"""BLE scanner daemon for tzc scale - saves all raw packets."""

import asyncio
import logging

import aioblescan

import db
from config import SCALE_NAME

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)


def parse_hci_packet(data: bytes) -> tuple[str | None, int | None, bytes | None]:
    """Parse raw HCI LE advertising packet.

    Returns (device_name, manufacturer_id, manufacturer_data) or (None, None, None).
    """
    if len(data) < 14 or data[0:2] != b'\x04\x3e':
        return None, None, None

    if data[3] != 0x02:  # Not LE Advertising Report
        return None, None, None

    adv_len = data[13]
    adv_data = data[14:14 + adv_len]

    device_name = None
    manufacturer_id = None
    manufacturer_data = None

    i = 0
    while i < len(adv_data):
        if i + 1 >= len(adv_data):
            break
        length = adv_data[i]
        if length == 0 or i + length >= len(adv_data):
            break
        ad_type = adv_data[i + 1]
        ad_value = adv_data[i + 2:i + 1 + length]

        if ad_type == 0x09:  # Complete Local Name
            try:
                device_name = ad_value.decode('utf-8')
            except:
                pass
        elif ad_type == 0xFF and len(ad_value) >= 2:  # Manufacturer Specific Data
            manufacturer_id = int.from_bytes(ad_value[0:2], "little")
            manufacturer_data = ad_value[2:]

        i += 1 + length

    return device_name, manufacturer_id, manufacturer_data


def process_hci_packet(data: bytes) -> None:
    """Process raw HCI packet - save if from scale."""
    device_name, manufacturer_id, manufacturer_data = parse_hci_packet(data)

    if device_name != SCALE_NAME:
        return

    if manufacturer_id is None or manufacturer_data is None:
        return

    # Save raw packet - that's all we do
    packet_hex = f"{manufacturer_id:04x}:{manufacturer_data.hex()}"
    db.save_raw_packet(packet_hex)
    log.debug("Saved: %s", packet_hex)


async def main() -> None:
    """Run the BLE scanner."""
    log.info("Initializing database...")
    db.init_db()

    log.info("Starting BLE scanner for '%s' scale...", SCALE_NAME)

    try:
        sock = aioblescan.create_bt_socket(0)
    except PermissionError:
        log.error("Permission denied. Need CAP_NET_RAW or root.")
        raise

    loop = asyncio.get_running_loop()
    conn, btctrl = await loop._create_connection_transport(
        sock, aioblescan.BLEScanRequester, None, None
    )

    btctrl.process = process_hci_packet
    await btctrl.send_scan_request()
    log.info("Scanning...")

    try:
        while True:
            await asyncio.sleep(1)
    finally:
        await btctrl.stop_scan_request()
        conn.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Stopped")
