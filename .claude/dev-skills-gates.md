# Dev Skills gate state
Track: release sequence — v0.1.0 (first release; no prior tags on remote)
Mode: manual
Version: 0.1.0
Updated: 2026-09-21
Branch: release/0.1.0 (from origin/main 171f4e4)

🔢 VERSION    ✅ manifest.json 0.1.0 = CHANGELOG [0.1.0]; remote has no tags (first release)
🔨 BUILD      ✅ pytest 20 passed on Python 3.14 (HA 2026.9.3); main CI green
🔒 SECURITY   ✅ 0 open — 0 Critical, 0 High
              ✅ code scan clean; pip-audit clean on 140 test pkgs; Dependabot alerts 200 (0)
              ✅ fixed 2026-09-21: control chars in GATT text (test fails without fix)
              🔕 waived 2026-09-21 by user: hacs/action@main + hassfest@master unpinned
                 (first-party validators, read-only jobs). Re-opens if either gets write access/secrets.
📄 DOCS       ✅ changelog dated; README notes untested-on-live-HA; hacs.json floor 2026.9.0
📦 RELEASE    ⏳ awaiting commit approval, PR, notes approval
🚀 SHIP       ⏳ plan: merge PR, user pushes tag v0.1.0, release.yml publishes
