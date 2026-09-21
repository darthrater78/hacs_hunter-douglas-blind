# Hunter Douglas PowerView BLE (Home Assistant / HACS)

Home Assistant custom integration for Hunter Douglas PowerView **Gen 3** shades over
Bluetooth LE — no Gateway, no Hunter Douglas account. Works through any HA Bluetooth
adapter or ESPHome Bluetooth proxy.

Framework and protocol source: [darthrater78/hunter-douglas-blind](https://github.com/darthrater78/hunter-douglas-blind)
(Android app; its `:protocol` module is ported here to Python — see [docs/PROTOCOL.md](docs/PROTOCOL.md)).

## Status

Read-only. Everything a shade shares **without encryption** becomes an entity; nothing can
move a shade yet (writes need a per-home keystream, which the framework builds last).

Per shade (one HA device per BLE address, grouped by PowerView home ID):

| Entity | Source | Notes |
|---|---|---|
| Position / Secondary position / Tilt | advertisement | only the rails the shade's type supports |
| Battery | GATT `0x2A19`, polled every 6 h | unavailable until a read succeeds |
| Type ID, Capability | advertisement | unknown types fall back to bottom-up |
| Status byte, RSSI, Raw advertisement | advertisement | diagnostic; RSSI, status byte and raw hex disabled by default |
| Device info (model, firmware, hardware, serial) | GATT `0x180A`, best effort | shown on the device page |
| Refresh battery (button) | GATT | reads battery and device info now; errors with the reason if it cannot (out of range, connection failed, no battery level). Automations can press it. |

Confirmed on a real Duette TDBU (2026-09-21): advertisement decode and the battery read (63%).
Running on a live Home Assistant 2026.9.3 install with an ESPHome Bluetooth proxy, the advertisement
sensors match the shade; the GATT reads (battery, device info) have not succeeded there yet, and the
Refresh battery button reports why.
Unconfirmed on hardware (see docs/PROTOCOL.md §8): Device Information characteristic set,
whether mains-powered shades expose battery, and the meaning of the status byte.
Position values are reported as broadcast (top-down shades are not inverted here).

## Install

HACS → Custom repositories → add this repo as an *Integration* (Home Assistant 2026.9.0 or newer), then restart HA.

## Development

```
python3.14 -m venv .venv && . .venv/bin/activate
pip install -r requirements_test.txt
pip install -r requirements_test_overrides.txt   # separate run: pip rejects the conflicting pin
pytest
```

The `protocol` tests (`tests/test_protocol.py`) are plain `unittest` and need no Home Assistant
install; `tests/test_hass.py` runs the config flow and sensors under pytest (Python 3.14, as the
current Home Assistant core requires).
CI runs HACS validation, hassfest and the tests. Releases: bump `manifest.json` version and
`CHANGELOG.md`, merge, then tag `vX.Y.Z` on the default branch.

## Security

Shade keystreams/AES keys grant control of your shades. Never commit them; store them via
HA's config entry storage only.

## License

MIT — see [LICENSE](LICENSE).
