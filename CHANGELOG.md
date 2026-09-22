# Changelog

## [0.3.0] - 2026-09-22

Diagnostics only. Nothing here makes a shade's battery readable; it makes a failed read explain itself,
after the v0.2.1 diagnosis turned out to rest on a misread log field.

### Added
- **GATT status** and **Last GATT attempt** diagnostic sensors per shade: the reason the last read failed
  (or `ok`) and when it ran, so a failing read is visible on the device page instead of only in the log
  and a button error.

### Changed
- Every connect attempt logs which radio it used (`via=<proxy MAC or adapter>`). With more than one proxy,
  or a dongle added later, "which radio was this?" is the first question about a failure.
- Retries re-resolve the Bluetooth device instead of reusing the one captured before the first attempt,
  so a retry can move to whichever adapter or proxy Home Assistant currently considers best.
- The connect warning is rate limited (a new reason, or once an hour) instead of once per shade per
  Home Assistant lifetime. Warning once kept whichever failure happened first -- typically a start-up
  race -- and hid every steady-state failure behind it at DEBUG.
- A poll stops before touching the radio when no connectable scanner is registered. Home Assistant answers
  from advertisement history, so a poll shortly after a restart would otherwise spend every attempt against
  a stack that has no radio yet.
- The **Refresh battery** button gives up after 20s of waiting behind another shade's read and says so,
  rather than blocking for as long as that read takes. Background polls still wait their turn.

### Fixed
- The connect-failure log said `connectable advert seen`, which describes the *scanner* that heard the
  shade rather than the shade's advertising PDU. It was being read as evidence the shade accepts
  connections, which it never was.

## [0.2.1] - 2026-09-21

### Changed
- A failed GATT connect now logs one WARNING per shade with the underlying error, the proxy's
  device details, RSSI and whether a connectable advert was seen, so the cause is visible
  without debug logging.
- The Refresh battery error includes the underlying error text, and connect attempts are
  capped at 3 so a press fails in seconds instead of after ~10 retries.

## [0.2.0] - 2026-09-21

### Added
- "Refresh battery" button per shade: connects now and reads the battery and device info, and
  fails with the reason (no adapter/proxy in range, connection failed, no readable battery level)
  instead of silently leaving the sensor unavailable until the next 6-hour poll.
  Automations can press it.

### Known limitations
- First live install (Home Assistant 2026.9.3, ESPHome Bluetooth proxy, Duette TDBU type 8): the
  advertisement sensors match the shade, but the GATT reads have not yet succeeded there. Battery
  stays unavailable and firmware/hardware/serial are empty. The Refresh battery button reports why.
- Still unconfirmed: which Device Information characteristics exist, whether mains-powered shades
  expose battery, the meaning of the status byte, and behaviour of type IDs other than 8.

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
