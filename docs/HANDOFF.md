# Handoff: HACS integration for Hunter Douglas PowerView Gen 3 (BLE)

Written 2026-09-21, after v0.2.1 shipped. Restart with dev-skills loaded (manual mode) and read this first.

**Goal:** Home Assistant custom integration (HACS), domain `hacs_hunter_douglas_blind`, that reads everything a
PowerView Gen 3 shade shares *without encryption* and exposes it as entities. Control (writes) is out of scope until
keystream onboarding exists.

## Current state

- **v0.1.0, v0.2.0 and v0.2.1 are released** (tags `v0.1.0` = `67169fa`, `v0.2.0` = `5e5cf0e`, `v0.2.1` = `63fbd9c`; GitHub releases, no assets).
  `main` is the default branch and holds all three. Repo: `darthrater78/hacs_hunter-douglas-blind`. HACS repo metadata
  (description, topics) and the icon are done; all three CI jobs (HACS, hassfest, pytest) are green.
- **Installed on the user's live Home Assistant** (2026.9.3, HA OS, ESPHome Bluetooth proxy, one shade: Duette TDBU type 8,
  home 63548, address ending `0851`). Verified through the read-only HA MCP:
  - Working: position 100, secondary 6.25, type 8, capability `top_down_bottom_up` (matches the real shade).
  - **Not working: the GATT reads.** Battery is `unavailable`, no firmware/hardware/serial (model falls back to
    "PowerView Gen 3 type 8"). Diagnosed 2026-09-21, see below.
- v0.2.0 added the **Refresh battery** button (per shade, diagnostic); it raises the reason a read failed.
- v0.2.1 (diagnostics only, no fix): the first GATT connect failure per shade logs a WARNING (error, proxy details,
  RSSI, connectable-advert seen), the button message includes the error text, connect attempts capped at 3.

## Diagnosis: the GATT connect fails at the radio level (not an integration bug)

- Live evidence: `Failed to connect ... Error ESP_GATT_ERROR`; ESPHome proxy log shows HCI `0x3E` (connection failed to
  be established), status 133, on every retry. The shade never answers the proxy's connect request.
- Ruled out: no connectable adapter (HA picks proxy `24:DC:C3:D1:51:3E`, `connectable advert seen=True`); address type
  (`address_type: 1` random, matches `C6:` static-random); Wi-Fi power save (`power_save_mode: NONE`, ESP-IDF
  `esp32-generic` package, active proxy); shade state (power-cycled, no change); the shade itself (the user's **phone
  connects fine**, and the framework app read 63% earlier).
- RSSI at the proxy is about -65 dBm; moving/extension-cabling did not help (RSSI unchanged, same proxy).
- Position/type/status work because they come from passive adverts; they say nothing about connectability.
- Conclusion: this ESP32 proxy cannot establish a link to the shade; a phone can.

- Tests: 24 pass under pytest on Python 3.14. `tests/test_protocol.py` is plain `unittest`; `tests/test_hass.py` needs pytest.

## Gate tracker

```
Track: none open (v0.2.1 SHIP done)    Mode: manual (say "auto mode" to change; never assume it)
🔢 VERSION ✅ 0.2.1   🔨 BUILD ✅   🔒 SECURITY ✅ 0 open   📄 DOCS ✅   📦 RELEASE ✅ #8   🚀 SHIP ✅ v0.2.1
🔕 waived 2026-09-21 by user: hacs/action@main + hassfest@master unpinned (first-party validators, read-only jobs).
   Re-opens if either gets write access or secrets.
```

`.claude/` is gitignored session scratch (the release PRs force-added the gate file). This table is the durable copy.

## Next step

1. Test a different radio: a **USB Bluetooth dongle on the HA host** (cleanest), or a different ESP32 board (S3/C3, real
   antenna) within 1-2 m of the shade, then press **Refresh battery** and read the log (`ha_get_logs` error_log, search
   `0851`). If a dongle reads the battery, the ESP32 is the cause; document it in the README.
2. If nothing but the phone connects, compare how the phone connects (nRF Connect: connection parameters, bonding, GATT
   cache) before changing code. Possible code-side ideas only after that: connection retry/backoff, longer timeout.
3. Optional ESPHome tuning to try: `esp32_ble_tracker: scan_parameters` (shorter scan window).
4. Once the read works: confirm Device Information characteristics (`2A29/24/25/26/27`) and whether the WARNING-once
   logging is still wanted.

Test env: `uv venv --python 3.14` then `uv pip install -r requirements_test.txt` (the system Python is 3.13, too old).

## Key files

- `custom_components/hacs_hunter_douglas_blind/hub.py`: advert callback, per-home hub, GATT poll (every 6 h, serialized by a lock); `async_poll_gatt` returns a failure reason or None.
- `.../button.py`: Refresh battery. `.../sensor.py`: sensor descriptions; battery unavailable until a read succeeds.
- `.../config_flow.py`: Bluetooth discovery + manual "pick a home in range"; unique ID is the homeId.
- `.../protocol/`: pure Python (no HA imports): `advertisement.py`, `capabilities.py`, `frame.py`.
- `docs/PROTOCOL.md`: copied from the framework repo `darthrater78/hunter-douglas-blind` (Android app; its `:protocol` module is what this ports).
- `.github/workflows/`: `ci.yml` (PR, main push; docs-only PRs skipped), `release.yml` (tag `v*`; requires a passing CI run on the tagged commit; notes from `CHANGELOG.md`).
- `requirements_test.txt` + `requirements_test_overrides.txt`: see decisions.

## Decisions to respect

- Read-only for now: no cover entities, no writes, no keystream handling. The framework builds writes last on purpose.
- The "velocity" byte is exposed raw as **Status byte** (a stationary shade reads `0xC0`, so it looks like flags).
- Position is reported as broadcast; nothing is inverted (only capability 6 is top-down inverted). Advert bytes 3-4 can exceed 4000; values are clamped to 100 and the raw hex is kept in a diagnostic sensor.
- Spoof hardening: at most 64 shades per home; GATT text is reduced to printable characters, 64 max.
- Test pins mirror Home Assistant core's bluetooth manifest and move **with core** (Dependabot ignores them). `cryptography` is overridden to 50.0.1 in a second pip run because core pins 48.0.1 (open advisories); test-only, never shipped.
- `hacs.json` minimum HA is 2026.9.0 (the tested version). CI must stay lean: one PR run and one `main` run per merge; the release gate needs the `main` run.
- Commit messages: Conventional Commits with the harness `Co-Authored-By` trailer. All work on branches, merged by PR. The user runs commits/pushes (manual mode); **tag pushes and ref deletions are always the user's**.

## Workflow gotchas learned

- There is no local `main` unless created (`git branch main origin/main`); `git switch -c x main` fails without it.
- Release flow that worked: bump manifest + dated changelog + gate file on `release/X.Y.Z`, PR, user merges, wait for CI on the merge commit, user runs the guarded tag block, then verify tag target, `release.yml`, and the release body.
- `release.yml` publishes no assets (no build artifact); notes are the `## [X.Y.Z]` changelog section.

## Confirmed vs assumed on hardware

Confirmed on the real Duette TDBU (type 8, home 63548): advertisement decode (`3C F8 08 00 30 FA 00 00 C0` -> primary 100 clamped, secondary 6.25, tilt 0, status 192), live in HA. The battery read (63%) was confirmed by the *framework app*, not yet by this integration.
**Unconfirmed:** which Device Information characteristics exist (`2A29/24/25/26/27` are best-effort), whether mains-powered shades expose battery, the status byte's meaning, and type IDs other than 8.

## Environment

Local session, Linux bash, `cd ~/hacs_hunter-douglas-blind`, host has Python 3.13 only. Tests need Python 3.14:
`pip install uv && uv venv --python 3.14 --seed .venv && . .venv/bin/activate && pip install -r requirements_test.txt && pip install -r requirements_test_overrides.txt && pytest`.
`/tmp` is a small tmpfs (~830 MB free): keep venvs on disk elsewhere, or a full install fails with "No space left on device".
The HA MCP (claude.ai HA) is read-only; it can inspect entities, logs and diagnostics but cannot install or restart anything.
