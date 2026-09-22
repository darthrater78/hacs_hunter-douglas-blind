# Handoff: HACS integration for Hunter Douglas PowerView Gen 3 (BLE)

Written 2026-09-22, after v0.3.0 shipped. Restart with dev-skills loaded (manual mode) and read this first.
**The v0.2.1 diagnosis in the previous handoff was wrong** -- see "What the live instance actually showed".

**Goal:** Home Assistant custom integration (HACS), domain `hacs_hunter_douglas_blind`, that reads everything a
PowerView Gen 3 shade shares *without encryption* and exposes it as entities. Control (writes) is out of scope until
keystream onboarding exists.

## Current state

- **v0.1.0, v0.2.0, v0.2.1 and v0.3.0 are released** (tags `v0.1.0` = `67169fa`, `v0.2.0` = `5e5cf0e`,
  `v0.2.1` = `63fbd9c`, `v0.3.0` = this release's merge commit; GitHub releases, no assets). `main` is the default
  branch and holds all of them. Repo: `darthrater78/hacs_hunter-douglas-blind`. HACS repo metadata
  (description, topics) and the icon are done; all three CI jobs (HACS, hassfest, pytest) are green.
- **Installed on the user's live Home Assistant** (2026.9.3, HA OS, ESPHome Bluetooth proxy, one shade: Duette TDBU type 8,
  home 63548, address ending `0851`). Verified through the read-only HA MCP:
  - Working: position 100, secondary 6.25, type 8, capability `top_down_bottom_up` (matches the real shade).
  - **Not working: the GATT reads.** Battery is `unavailable`, no firmware/hardware/serial (model falls back to
    "PowerView Gen 3 type 8"). **Still unresolved** -- see below for what was and was not established.
- v0.2.0 added the **Refresh battery** button (per shade, diagnostic); it raises the reason a read failed.
- v0.2.1 (diagnostics only, no fix): the first GATT connect failure per shade logs a WARNING (error, proxy details,
  RSSI, connectable-advert seen), the button message includes the error text, connect attempts capped at 3.
- v0.3.0 (diagnostics, still no fix): `GATT status` and `Last GATT attempt` sensors carry the outcome, every attempt
  logs which radio it used, retries re-resolve the radio, the connect warning is rate limited rather than once-ever,
  and a poll stops before the radio when no connectable scanner is registered.

## What the live instance actually showed (2026-09-22, corrected)

The v0.2.1 handoff concluded "this ESP32 proxy cannot establish a link; a phone can". That conclusion rests on **one
event, from one radio**, and two of its supporting claims were wrong. Read this before repeating it.

**Three different failures had been conflated:**

| When | Log | What it actually was |
|---|---|---|
| 2026-09-21 10:38 local | `ESP_GATT_ERROR`, HCI `0x3E`, status 133 | the real BLE-level question -- still open |
| 2026-09-21 15:25 local | `0 scanner(s) registered, 0 scanning, 0 connectable` | a poll 43s after an HA restart, before any proxy registered |
| 2026-09-21 19:08 onward | no adverts at all | a LAN outage: DNS timeouts, several `10.0.0.x` hosts unreachable, every ESPHome proxy gone |

Only the first is about the shade.

**Why this was hard to see:** the v0.2.1 warning was once-per-shade-per-HA-lifetime, so the log kept whichever failure
came first after a restart -- systematically the start-up race -- and demoted every later one to DEBUG. v0.3.0 rate
limits it instead.

**Corrections to the earlier "ruled out" list:**

- `connectable advert seen=True` does **not** rule out an advert-side cause. In Home Assistant that flag is a property
  of the *scanner* that received the advertisement, not of the shade's advertising PDU. It says a connection-capable
  radio heard the shade; it says nothing about whether the shade accepts connections. HA cannot see PDU type at all --
  nRF Connect on a phone can.
- There is **one** Bluetooth proxy, not a fleet. `Bluetooth Proxy-1` (`esp32-bluetooth-proxy-50cb20`, 10.0.0.196) was
  deleted; its entities may still linger in the registry. Every data point ever collected -- -59, -65 and -76 dBm, the
  `ESP_GATT_ERROR`, the `0x3E` -- comes from `btp-1` (`24:DC:C3:D1:51:3E`) alone. With no second radio, "this ESP32
  cannot connect" and "the shade will not accept this central" have never been distinguishable.

**Still standing:** address type (`address_type: 1` random, matches `C6:` static-random) is genuinely ruled out, and
position/type/status come from passive adverts, so they say nothing about connectability.

**Live hypotheses, none eliminated:**

1. Wi-Fi/BLE coexistence on the ESP32 -- one radio, and the connect handshake needs precise timing that scanning does not.
2. The shade filters connections (accept list / bonding). The phone that enrolled the shades in the official PowerView
   app holds a bond; an ESP32 never will, and ESPHome proxies cannot pair at all. If this is the cause, no proxy tuning
   or dongle fixes it without pairing from a local adapter.
3. The shade is only connectable in a narrow window. ESPHome's default scan is ~30ms every 320ms; a phone scans continuously.

- Tests: 35 pass under pytest on Python 3.14. `tests/test_protocol.py` is plain `unittest`; `tests/test_hass.py` needs pytest.

## Gate tracker

```
Track: none open (v0.3.0 SHIP done)    Mode: manual (say "auto mode" to change; never assume it)
🔢 VERSION ✅ 0.3.0   🔨 BUILD ✅   🔒 SECURITY ✅ 0 open   📄 DOCS ✅   📦 RELEASE ✅   🚀 SHIP ✅ v0.3.0
🔕 waived 2026-09-21 by user: hacs/action@main + hassfest@master unpinned (first-party validators, read-only jobs).
   Re-opens if either gets write access or secrets.
```

`.claude/` is gitignored session scratch (the release PRs force-added the gate file). This table is the durable copy.

## Next step

Nothing here needs code. The next move is to break the tie between the three hypotheses above, cheapest first:

1. **Move `btp-1` to within 1-2 m of the shade** and press **Refresh battery**. Free. The shade has been read at -59 to
   -76 dBm; if a strong link connects, it is the radio and the answer is placement or a better board. If it still fails
   at ~-50 dBm, link quality is eliminated. Read `GATT status` on the shade's device page -- v0.3.0 puts the reason
   there, so this no longer needs the log.
2. **Try a device that has never run the official PowerView app** (a second phone or tablet, nRF Connect, next to the
   shade). If it connects, the shade accepts strangers and hypothesis 2 is dead. If it fails the same way, the shade
   only talks to enrolled centrals -- and no ESPHome proxy will ever qualify, because proxies cannot pair. While there,
   note whether the advert is flagged CONNECTABLE and its interval; that settles hypothesis 3, and HA cannot see either.
3. **USB Bluetooth dongle on the HA host** -- the definitive radio test, but note HA runs as a **KVM guest** on a
   Proxmox host, so it needs USB passthrough into the VM first. If pairing turns out to be required (hypothesis 2),
   a local adapter is the only thing that can do it: `establish_connection` takes `pair=True`.
4. Optional while waiting: ESPHome scan-duty tuning (`esp32_ble_tracker: scan_parameters`). Low expected value.
5. Once a read succeeds: confirm which Device Information characteristics exist (`2A29/24/25/26/27`).

Housekeeping: `Bluetooth Proxy-1` was deleted but its entities may still be in the registry -- removing that ESPHome
config entry stops the stale `unavailable` entities and the reconnect noise.

Test env: `uv venv --python 3.14` then `uv pip install -r requirements_test.txt`. **The pinned core needs Python
>= 3.14.2**, and a cloud container whose `uv` only offers 3.14.0rc2 cannot build this environment at all --
`--ignore-requires-python` resolves a set that crashes on import. CI (Python 3.14, `ci.yml`) is then the only runner,
so expect to push and read the CI log rather than testing locally.

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
