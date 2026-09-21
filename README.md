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

Confirmed on a real Duette TDBU (2026-09-21): advertisement decode and the battery read (63%).
Unconfirmed on hardware (see docs/PROTOCOL.md §8): Device Information characteristic set,
whether mains-powered shades expose battery, and the meaning of the status byte.
Position values are reported as broadcast (top-down shades are not inverted here).

## Install

HACS → Custom repositories → add this repo as an *Integration*, then restart HA.

## Development

```
python3 -m unittest discover tests -v
```

The `protocol` package has no Home Assistant imports so it tests without an HA install.
CI runs HACS validation, hassfest and the tests. Releases: bump `manifest.json` version and
`CHANGELOG.md`, merge, then tag `vX.Y.Z` on the default branch.

## Security

Shade keystreams/AES keys grant control of your shades. Never commit them; store them via
HA's config entry storage only.
