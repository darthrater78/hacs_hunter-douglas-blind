# Changelog

## [Unreleased]

### Added
- "Refresh battery" button per shade: connects now and reads the battery and device info, and
  fails with the reason (no adapter/proxy in range, connection failed, no readable battery level)
  instead of silently leaving the sensor unavailable until the next 6-hour poll.

## [0.1.0] - 2026-09-21

First release. Read-only: everything a PowerView Gen 3 shade shares without
encryption becomes a Home Assistant entity. Nothing can move a shade yet.

### Added
- Bluetooth-discovered and manual (scan-based) config flows, one entry per PowerView home.
- Sensors for all unencrypted data: position, secondary position, tilt, battery, type ID,
  capability, status byte, RSSI and raw advertisement; device info (model, firmware,
  hardware, serial) on the device page.
- Pure-Python `protocol` package (advertisement parsing, command frame builder) ported from
  darthrater78/hunter-douglas-blind.
- Home Assistant tests (config flow, entity creation, live updates, GATT battery and device info,
  spoof cap) plus protocol unit tests; CI runs HACS validation, hassfest and pytest on Python 3.14.
- Tag-gated release workflow that requires a passing CI run and builds notes from this file.
- Integration icon (`brand/icon.png`, 256x256), which HACS validation requires.
- MIT `LICENSE`.

### Security
- GATT text (device info) is reduced to printable characters and 64 characters, because a spoofed
  device can advertise a matching home ID.
- At most 64 shades are tracked per home, so spoofed advertisements cannot create unbounded entities.
- Test-only `cryptography` is overridden to 50.0.1 via `requirements_test_overrides.txt`
  (Home Assistant core pins 48.0.1, which has open advisories). Nothing here ships with the integration.

### Changed
- Dependabot ignores the Bluetooth test pins that mirror Home Assistant core's manifest; they move
  with core, not on their own.
- `hacs.json` minimum Home Assistant raised from 2024.6.0 to 2026.9.0, the version the tests run on
  (the code also needs 2024.8 or newer for `DeviceInfo.model_id`).

### Known limitations
- Not yet run against a live Home Assistant install. Confirmed on real hardware only for the
  advertisement decode and battery read (Duette TDBU, type 8).
- Unconfirmed: which Device Information characteristics exist, whether mains-powered shades expose
  battery, the meaning of the status byte, and behaviour of type IDs other than 8.
