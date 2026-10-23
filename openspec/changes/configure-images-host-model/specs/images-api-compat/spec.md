## ADDED Requirements

### Requirement: Configurable image host model

The system SHALL select the internal Responses host for image generation and editing from `CODEX_LB_IMAGES_HOST_MODEL`, defaulting to `gpt-6-astra`. This setting MUST NOT replace the requested public `gpt-image-*` renderer, weaken account eligibility checks, or change public model policy and accounting. The setting MUST apply equally to `/v1/images/*` and `/backend-api/codex/images/*` aliases.

#### Scenario: Configured host preserves the image renderer

- **WHEN** the deployment selects an eligible Responses host and a client requests an image renderer
- **THEN** the upstream Responses request uses that configured host
- **AND** the `image_generation` tool retains the requested renderer and image parameters

#### Scenario: Unavailable configured host fails explicitly

- **WHEN** no account supports the configured host
- **THEN** the existing model-eligibility error is returned without silently substituting another host or image renderer
