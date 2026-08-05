## 1. Contract

- [x] 1.1 Record the observed session-bridge cooldown failure and the scoped XA
  native mitigation.
- [x] 1.2 Add the Windows desktop capability delta and operator context.

## 2. Implementation

- [x] 2.1 Make ordinary owned-backend launches set the canonical bridge-enable
  environment variable to `false`.
- [x] 2.2 Remove the now-redundant self-test-only copy of the same environment
  override.
- [x] 2.3 Document the owned-backend direct HTTP policy in existing XA Windows
  application documentation.

## 3. Verification

- [x] 3.1 Add source-contract coverage for ordinary launch scope and duplicate
  environment handling.
- [x] 3.2 Run XA lint/tests, strict OpenSpec validation, and `git diff --check`.
- [x] 3.3 Rebuild the native release and perform live acceptance without
  terminating unrelated clients.
