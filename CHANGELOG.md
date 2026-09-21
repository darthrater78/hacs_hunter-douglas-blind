# Changelog

## [0.1.0] - Unreleased

### Added
- Dependabot ignores the Bluetooth test pins that mirror Home Assistant core's manifest; they move with core, not on their own.
- MIT `LICENSE`.
- `requirements_test_overrides.txt`: test-only `cryptography` 50.0.1 (Home Assistant core pins 48.0.1, which has open advisories); CI installs it as a second step.
- Home Assistant tests (config flow, entity creation, live updates, GATT battery/device-info, spoof cap) and `requirements_test.txt`; CI now runs pytest on Python 3.14.
- Sensors for all unencrypted data: position, secondary, tilt, battery, type, capability, status byte, RSSI, raw advertisement; device info on the device page.
- Manual (scan-based) and Bluetooth-discovery config flows.
- Initial HACS scaffold: Bluetooth-discovered config flow (one entry per PowerView home),
  pure-Python `protocol` package (advertisement parsing, command frame builder) ported
  from darthrater78/hunter-douglas-blind, unit tests, CI (HACS, hassfest, tests),
  tag-gated release workflow.
