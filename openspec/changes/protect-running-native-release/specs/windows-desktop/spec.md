## ADDED Requirements

### Requirement: Builder preserves running native releases

The builder MUST inspect the executable paths of native hosts and backends before recursively cleaning an approved output directory. It MUST refuse cleanup when a matching process runs from that directory or process inspection fails. When the default release is running, release assembly MUST create a new uniquely named sibling directory under `xa-app/release/`, verify that assembled directory, and report its executable and backend paths. It MUST retain the active process and release files. A requested automatic launch MUST be deferred while any native release under the release root is running.

#### Scenario: Default release is active

- **GIVEN** a native host or backend is running from `xa-app/release/Codex LB/`
- **WHEN** release assembly starts
- **THEN** the build writes and verifies a new sibling staged release
- **AND** no files are removed from the active release

#### Scenario: Default release is idle

- **GIVEN** no native host or backend runs from the default release directory
- **WHEN** release assembly starts
- **THEN** the build assembles the default release and reports its actual executable path

#### Scenario: Process inspection is unavailable

- **WHEN** process inspection fails or cannot identify a listed native process's executable path
- **THEN** the builder fails before recursively deleting the target directory

#### Scenario: Unrelated release does not block cleanup

- **GIVEN** a native host or backend runs from a different directory outside the cleanup target
- **WHEN** the builder checks the approved cleanup target
- **THEN** that unrelated process does not block cleanup

#### Scenario: Automatic launch would reuse an old backend

- **GIVEN** another native release under `xa-app/release/` is running
- **WHEN** a build requested with `--run` completes verification
- **THEN** it reports the staged executable and defers launch until the operator closes the active release
