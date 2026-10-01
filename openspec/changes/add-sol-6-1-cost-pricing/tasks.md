## Implementation

- [x] Add regression coverage for aliases, cached-input components, tiers, and the exclusive long-context boundary.
- [x] Add GPT-6.1 Sol pricing and suffixed alias resolution using the existing calculator.
- [x] Verify persistence, request-log display, and usage-summary totals with isolated test data.
- [x] Run focused backend and XA tests, lint, strict OpenSpec validation, and Markdown formatting checks.

Validation on 2026-09-30: all 27 new pricing unit cases reproduced the missing model before implementation. The final focused run passed 147 tests across pricing, request-log repository, usage-summary integration, and XA app tests, including 37 new GPT-6.1 Sol cases. Ruff lint and formatting checks passed. Strict validation of this change passed with no issues. Repository-wide strict validation returned 211 passed and 42 failed existing items; unrelated placeholder purposes and existing delta-spec errors remain outside this change. Test data and encryption keys used temporary directories; no live database was modified.

## Operator acceptance

- [ ] Rebuild and restart after active sessions finish; verify a newly completed GPT-6.1 Sol request displays its estimated cost.

From the repository root, the operator build command is `python xa-app\build.py --no-pause`. The operator's build completed compilation but hit a locked file during release assembly while the authenticated app was running. Assembly was subsequently recovered into `xa-app/release/Codex LB staged 20260930-122959-440436/`, whose bundled pricing and all nine isolated packaged checks passed. The active app/backend remain running; actual GPT-6.1 Sol request acceptance in the operator session is still pending. See the `protect-running-native-release` change for the guarded staging fix. Leave this change active until operator acceptance is complete.
