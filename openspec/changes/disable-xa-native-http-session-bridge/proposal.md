## Why

The upstream HTTP Responses session bridge can enter a continuity-bound retry
circuit after an upstream WebSocket closes or stops acknowledging
`response.create`. Codex clients then receive repeated local 503 cooldown
responses even though the account, database, dashboard, and ordinary HTTP
Responses path remain healthy. The XA native application needs a reliable
packaged default while the upstream stale-anchor recovery fix remains
unmerged and its bridge integration checks are not green.

## What Changes

- Make the XA native launcher disable the internal HTTP Responses session
  bridge whenever it starts its owned bundled backend.
- Keep the ordinary direct HTTP Responses retry and account-routing path
  enabled.
- Leave separately running healthy codex-lb services unchanged when the native
  window reuses them.
- Add a native source-contract regression and document the packaged runtime
  policy.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `windows-desktop`

## Impact

- **Native runtime:** the owned packaged backend receives
  `CODEX_LB_HTTP_RESPONSES_SESSION_BRIDGE_ENABLED=false` from the C++ host.
- **Proxy behavior:** XA-packaged HTTP Responses traffic uses the existing
  direct HTTP streaming/retry path instead of the internal upstream WebSocket
  session bridge.
- **External services:** a healthy service already listening on the selected
  port is reused without configuration changes.
- **Build:** no dependency, database, packaging, or version change is required.

