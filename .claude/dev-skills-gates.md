# Dev Skills gate state
Track: work commit — GATT diagnostics on the battery read (no version bump, no tag)
Mode: manual
Version: 0.2.1 (released; tag v0.2.1 = 63fbd9c on remote)
Updated: 2026-09-22
Branch: claude/blinds-battery-mobile-read-t40ev8 (from main 2208c0c)
Env: remote container — Claude executes git after approval

🔢 VERSION    ⬜ not owed on a work commit
🔨 BUILD      ⬜ cannot run here: uv offers only CPython 3.14.0rc2, the pins need >=3.14.2
              tests/test_protocol.py 10 passed; every module compiles on 3.14
              tests/test_hass.py (22 tests, 7 new) unrun locally — CI runs pytest on 3.14
🔒 SECURITY   ✅ 0 open — 0 Critical, 0 High
              scan of the diff: 1 finding found and fixed (BLE error text reaching
              entity state now goes through _printable, as GATT text already did)
              pip-audit on the installed env: no known vulnerabilities; no dependency change
📄 DOCS       ⬜ not owed on a work commit
📦 RELEASE    ⬜
🚀 SHIP       ⬜
              v0.2.1 SHIP ✅ (tag + release verified in the prior session)

Waivers carried forward: 🔕 2026-09-21 by user — hacs/action@main + hassfest@master
unpinned (first-party validators, read-only jobs). Re-opens on write access/secrets.
