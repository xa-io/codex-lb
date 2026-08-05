## ADDED Requirements

### Requirement: XA-owned backend uses the reliable direct Responses path

When the native launcher starts its bundled backend, it MUST set
`CODEX_LB_HTTP_RESPONSES_SESSION_BRIDGE_ENABLED` to `false` for that child so
HTTP Responses traffic uses the existing direct HTTP streaming and retry path.
This launch policy MUST apply during ordinary operation as well as packaged
self-tests. The launcher MUST NOT change the configuration of a healthy
codex-lb service that it reuses instead of starting.

#### Scenario: Native launcher starts its bundled backend

- **GIVEN** the selected loopback port is unused
- **WHEN** the operator launches the XA native application
- **THEN** the owned bundled backend starts with the HTTP Responses session bridge disabled
- **AND** Codex HTTP Responses requests continue through the direct account-routing path

#### Scenario: Native launcher reuses an existing service

- **GIVEN** a healthy codex-lb service already owns the selected loopback port
- **WHEN** the operator launches the XA native application
- **THEN** the native window reuses that service
- **AND** it does not alter the reused service's session-bridge configuration

