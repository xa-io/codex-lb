## Implementation

- [x] Cover cleanup refusal, exact-path process matching, process-inspection failure, and staged release assembly with regression tests.
- [x] Guard cleanup and stage a sibling release when the default release is running.
- [x] Verify and report the actual output path and defer automatic launch while a release is active.
- [x] Assemble the completed build outputs and run the isolated packaged self-test.
- [x] Run source tests, lint, strict change validation, and Markdown formatting checks; confirm active process identity and health remain unchanged.

Validation on 2026-09-30: the initial 11 new build-safety cases failed before implementation. The focused pricing, request-log, usage-summary, and XA source suite then passed 158 tests. Two additional cleanup/process-query failure regressions brought the final XA suite to 27 passing tests. Ruff lint/formatting and strict validation of this change passed. All nine isolated packaged checks passed, including health, readiness, dashboard HTML/assets/API, persistence initialization, encryption key creation, and graceful shutdown. Native PE inspection confirmed x64 GUI output, and the prohibited-file release scan was empty.

Recovery output: `xa-app/release/Codex LB staged 20260930-122959-440436/Codex LB.exe`. The compiled backend's extracted pricing code resolved GPT-6.1 Sol at Standard USD 2/0.10/10 per million tokens and correctly calculated Standard/Flex/Priority long-context totals of USD 0.59/0.295/1.18 for the documented example. The original native/backend PIDs remained 190872/224408, all 1,290 remaining active-release files retained their names/sizes/modification times, and live health/readiness stayed HTTP 200. No running process was stopped or restarted.

## Operator acceptance

- [ ] After active sessions finish, close the current app and launch the verified staged release; confirm new GPT-6.1 Sol requests show estimated cost.
