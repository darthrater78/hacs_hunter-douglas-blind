"""Constants for the Hunter Douglas PowerView BLE integration."""

from datetime import timedelta

DOMAIN = "hacs_hunter_douglas_blind"

# Bluetooth SIG company identifier for Hunter Douglas (0x0819).
MANUFACTURER_ID = 0x0819

CONF_HOME_ID = "home_id"

# Battery / Device Information need a GATT connection, so they are polled, not
# pushed. Position and tilt arrive for free in advertisements.
GATT_POLL_INTERVAL = timedelta(hours=6)

# Standard GATT (docs/PROTOCOL.md §1). Device Information characteristics are
# best-effort: the framework confirmed only the Battery read on real hardware.
CHAR_BATTERY_LEVEL = "00002a19-0000-1000-8000-00805f9b34fb"
DEVICE_INFO_CHARS = {
    "manufacturer": "00002a29-0000-1000-8000-00805f9b34fb",
    "model": "00002a24-0000-1000-8000-00805f9b34fb",
    "serial": "00002a25-0000-1000-8000-00805f9b34fb",
    "firmware": "00002a26-0000-1000-8000-00805f9b34fb",
    "hardware": "00002a27-0000-1000-8000-00805f9b34fb",
}

# Upper bound on shades tracked per home (spoofed advertisements must not create unbounded entities).
MAX_SHADES = 64
