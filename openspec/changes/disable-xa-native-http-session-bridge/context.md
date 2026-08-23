# XA native HTTP session-bridge mitigation

## Decision

The native host owns the reliability policy only for the backend process it
creates. It sets the canonical codex-lb environment variable
`CODEX_LB_HTTP_RESPONSES_SESSION_BRIDGE_ENABLED` to `false` before creating the
bundled backend process, then restores its own environment exactly as it does
for the owned port and data directory values.

This keeps account selection, authentication, request logging, usage tracking,
and the external HTTP/SSE contract intact. The backend falls through to its
existing direct HTTP streaming and retry implementation. No proxy hot-path
fork is added to XA source.

## Constraints

- The launcher must not modify or restart a healthy service that it reuses.
- The bridge-off value must apply during ordinary launches, not only packaged
  self-tests.
- The same environment name must appear only once in the native child setup so
  save/restore ordering cannot leave the host process with the wrong value.
- The mitigation remains explicit and removable after the upstream durable
  stale-anchor recovery is merged and verified.

## Failure mode

With the bridge enabled, an upstream connection can close before completion and
the replacement can fail to acknowledge `response.create`. The durable session
then remains continuity-bound while its retry circuit is cooling down, so Codex
retries receive repeated `upstream_request_timeout` 503 responses.

## Concrete example

An operator launches the rebuilt `Codex LB.exe` while port 2455 is unused. The
native host starts its packaged backend with the session bridge disabled. A
Codex request to `/backend-api/codex/responses` still selects the configured
account and streams normally through the direct HTTP path, without creating an
HTTP bridge session or entering its cooldown circuit.
