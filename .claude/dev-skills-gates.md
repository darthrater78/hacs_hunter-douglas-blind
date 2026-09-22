# Dev Skills gate state
Track: release sequence — v0.3.0 (previous v0.2.1 tagged on remote at 63fbd9c)
Mode: manual
Version: 0.3.0
Updated: 2026-09-22
Branch: claude/blinds-battery-mobile-read-t40ev8 (restarted from main 6d1a300 after PR #10 merged)
Env: remote container — Claude executes git after approval; tag push is the user's

🔢 VERSION    ✅ manifest 0.3.0 = CHANGELOG [0.3.0]; v0.2.1 on remote; MINOR because
              d9c5605 is a feat: since the tag. Bump confirmed by the user 2026-09-22.
🔨 BUILD      ✅ CI-only — structural: uv here offers only CPython 3.14.0rc2, the pins
              need >= 3.14.2; --ignore-requires-python yields a set that crashes on import.
              Checked locally: test_protocol 10 passed, all modules compile on 3.14,
              every JSON parsed, tree unchanged across the run. CI must be green pre-merge.
🔒 SECURITY   ✅ 0 open — 0 Critical, 0 High
              diff scan clean; no dependency change since the clean pip-audit run;
              async_scanner_count verified present in the pinned HA source
📄 DOCS       ✅ CHANGELOG [0.3.0] dated; README entity table + status updated;
              docs/HANDOFF.md corrected (the v0.2.1 diagnosis was wrong)
📦 RELEASE    ⏳ awaiting commit approval, then push + PR + CI
🚀 SHIP       ⏳ plan: merge the release PR, user runs the tag block, release.yml publishes
              v0.2.1 SHIP ✅ (verified in the prior session)

Waivers carried forward: 🔕 2026-09-21 by user — hacs/action@main + hassfest@master
unpinned (first-party validators, read-only jobs). Re-opens on write access/secrets.
