"""Constants for the Hunter Douglas PowerView BLE integration."""

from datetime import timedelta

DOMAIN = "hacs_hunter_douglas_blind"

# Bluetooth SIG company identifier for Hunter Douglas (0x0819).
MANUFACTURER_ID = 0x0819

CONF_HOME_ID = "home_id"

# Battery / Device Information need a GATT connection, so they are polled, not
# pushed. Position and tilt arrive for free in advertisements.
GATT_POLL_INTERVAL = timedelta(hours=6)

# Retries inside one poll. Each attempt is a full connect cycle, so this is the
# difference between a slow read and a shade that holds the radio for a minute.
CONNECT_ATTEMPTS = 3

# How long a read someone is waiting on (the Refresh battery button) queues
# behind another shade's read before it reports back instead. Long enough for a
# normal connect/read to finish; short enough to beat a user pressing again.
MANUAL_POLL_WAIT = 20.0

# How often the same failure may warn again. Warning only once per shade per
# Home Assistant lifetime keeps whichever failure happened first -- typically a
# start-up race, before any proxy has registered -- and hides every steady-state
# failure behind it at DEBUG.
WARN_INTERVAL = timedelta(hours=1)

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
