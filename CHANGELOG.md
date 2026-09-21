# Changelog

## [0.1.0] - Unreleased

### Added
- Sensors for all unencrypted data: position, secondary, tilt, battery, type, capability, status byte, RSSI, raw advertisement; device info on the device page.
- Manual (scan-based) and Bluetooth-discovery config flows.
- Initial HACS scaffold: Bluetooth-discovered config flow (one entry per PowerView home),
  pure-Python `protocol` package (advertisement parsing, command frame builder) ported
  from darthrater78/hunter-douglas-blind, unit tests, CI (HACS, hassfest, tests),
  tag-gated release workflow.
