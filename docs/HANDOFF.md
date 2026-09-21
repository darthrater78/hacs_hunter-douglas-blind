# Handoff: HACS integration for Hunter Douglas PowerView Gen 3 (BLE)

Written 2026-09-21. Restart the session with dev-skills loaded (manual mode) and read this first.

**Goal:** Home Assistant custom integration (HACS), domain `hacs_hunter_douglas_blind`, that reads
everything a PowerView Gen 3 shade shares *without encryption* and exposes it as entities. Control
(writes) is out of scope until keystream onboarding exists.

## Current state

- Branch `feat/init-hacs-scaffold`. **Local only, never pushed.** The remote has no branches or tags
  and no default branch yet. `origin` is `https://github.com/darthrater78/hacs_hunter-douglas-blind`.
- Commit `1404d04` (scaffold + sensors) exists locally.
- **Uncommitted** (awaiting approval): HA tests, `pytest.ini`, `requirements_test.txt`, CI change
  (pytest on Python 3.14), Dependabot pip entry, README/CHANGELOG edits, this file.
- Tests: 19 pass under pytest on Python 3.13 (old HA core) and 3.14 (HA 2026.9.3).
  `tests/test_protocol.py` is plain `unittest`; `tests/test_hass.py` needs pytest and the HA tooling.
- **Never run against real Home Assistant, a real shade, hassfest, HACS validation, or CI.**
  The Home Assistant MCP was reported "up" (read-only) but was not visible to the previous session.
  Check `/mcp` first; if it is visible, use it read-only to compare entities with the real shades.

## Gate tracker

```
Track: work commit    Mode: manual (say "auto mode" to change; never assume it)
🔢 VERSION    ⬜ not owed (work commit)
🔨 BUILD      ⬜ not owed (work commit)
🔒 SECURITY   ⏳ 1 open — 0 Critical, 0 High (blocks the release track, not a work commit)
              ✅ fixed: broad excepts narrowed, GATT lock, MAX_SHADES=64 bound, empty battery payload
              ✅ fixed: Dependabot alerts enabled (endpoint returns 200 [])
              🔕 waived 2026-09-21 by user: hacs/action@main + hassfest@master unpinned
                 (first-party validators, read-only jobs). Re-opens if either gets write access/secrets.
              📝 OPEN: cryptography 48.0.1 in requirements_test.txt — 3 advisories (fix 49.0.0/50.0.0).
                 Test-only, pinned exactly by HA core 2026.9.3, never shipped. Needs the USER's decision:
                 waive with a reason, or wait for the next HA core bump (Dependabot pip is watching).
📄 DOCS       ⬜ not owed (work commit)
📦 RELEASE    ⬜
🚀 SHIP       ⬜
```

`.claude/dev-skills-gates.md` is gitignored session scratch; this table is the durable copy.

## Pending decisions for the user

1. Approve committing the tests + CI changes, e.g. `test: add home assistant tests and pytest ci`
   (commits need explicit approval; present the block, do not run it, in manual mode).
2. Waive or hold the `cryptography` finding (above). Claude must not waive it.
3. No `LICENSE` yet; the framework repo's licence was not stated in what was read.
4. Default branch: none on the remote. CI and the release gate assume `main`/`master`.

## Key files

- `custom_components/hacs_hunter_douglas_blind/hub.py` — advert callback, per-home hub, GATT poll (battery + device info, every 6 h, serialized by a lock).
- `.../sensor.py` — sensor descriptions; rails gated by capability; battery unavailable until a read succeeds.
- `.../config_flow.py` — Bluetooth discovery + manual "pick a home in range"; unique ID is the homeId.
- `.../protocol/` — pure Python (no HA imports): `advertisement.py`, `capabilities.py`, `frame.py`.
- `docs/PROTOCOL.md` — copied from the framework repo `darthrater78/hunter-douglas-blind` (Android app; its `:protocol` module is what this ports).
- `.github/workflows/ci.yml`, `release.yml` — patterned on `darthrater78/HA-Stock-App` (release gate needs a passing CI run for the tagged commit; notes come from `CHANGELOG.md`).
- `tests/conftest.py` — builds real `BluetoothServiceInfoBleak` objects; `tests/test_hass.py` patches the HA Bluetooth calls.

## Decisions to respect

- Read-only for now: no cover entities, no writes, no keystream handling. The framework builds writes last on purpose.
- The "velocity" byte is exposed raw as **Status byte**: a stationary shade reads `0xC0`, so it looks like flags.
- Position is reported as broadcast; nothing is inverted (only capability 6 is top-down inverted).
- Advertisement bytes 3–4 can exceed 4000 (raw `0x3000` → 307%); values are clamped to 100 and the raw hex is kept in a diagnostic sensor.
- Unpinned `hacs/action@main` / `hassfest@master` are an accepted waiver; everything else in workflows stays SHA-pinned.
- Test deps: `requirements_test.txt` pins `pytest-homeassistant-custom-component` (which pins HA core) and HA's Bluetooth requirements copied from that core's manifests. Bump them together, on Python 3.14.
- Commit messages: Conventional Commits, with the `Co-Authored-By` trailer given by the harness.

## Confirmed vs assumed on hardware

Confirmed on a real Duette TDBU (type 8, home 63548, 2026-09-21): advertisement decode, and the battery read (63%).
**Unconfirmed:** which Device Information characteristics exist (`2A29/24/25/26/27` are best-effort), whether
mains-powered shades expose battery, what the status byte means, and behaviour of type IDs other than 8.
Real sample: `3C F8 08 00 30 FA 00 00 C0` → primary 100 (clamped), secondary 6.25, tilt 0, status 192.

## Shell environment

Local session, Linux bash, `cd ~/hacs_hunter-douglas-blind`. Git commands are presented for the user to run (manual mode);
tag pushes and ref deletions are always the user's. Work happens on branches, never directly on `main`.
The scratch venvs used for testing lived in the session scratchpad and are gone; recreate with
`python3.14 -m venv .venv && . .venv/bin/activate && pip install -r requirements_test.txt && pytest`
(needs Python 3.14; `uv venv --python 3.14` works if it is not installed).

## Next step

Get the two decisions above, then commit the pending work. After that, verify against real hardware / the HA MCP,
then consider a 0.1.0 release sequence (version bump, docs, PR, tag) once entities have run on a real install.
