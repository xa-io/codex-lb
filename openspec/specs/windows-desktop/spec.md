# windows-desktop Specification

## Purpose
Define the build, runtime, ownership, branding, data-preservation, and verification contract for the XA native Windows application.
## Requirements
### Requirement: XA desktop product source is native and self-contained

The fork MUST keep the desktop application's C++ source, CMake definitions,
Windows resources, dependency pins, backend packaging definition, tests, build
script, and build documentation under the tracked `xa-app/` directory. The
visible `Codex LB.exe` process MUST be a native C++ Windows application and MUST
NOT depend on pywebview or a Python GUI entry point.

#### Scenario: Contributor inspects the application folder

- **WHEN** a contributor opens `xa-app/`
- **THEN** the folder contains all open source files needed to build the native application
- **AND** `xa-app/build.py` documents and performs the supported build/run workflow

### Requirement: Native window hosts the existing dashboard

The C++ application MUST create a persistent native Win32 window, initialize the
Microsoft Edge WebView2 control, show a loading document immediately, and
navigate to the existing codex-lb dashboard only after the service passes its
health identity contract. It MUST show actionable errors inside the native
window when WebView2, the backend, or the configured port is unavailable.

#### Scenario: Operator launches the native executable

- **WHEN** an operator double-clicks `Codex LB.exe`
- **THEN** a native loading window appears without a console or separate browser
- **AND** the live dashboard replaces the loading view after backend readiness

### Requirement: Native launcher owns only the backend it starts

The native launcher MUST reuse a healthy codex-lb service on the configured
loopback port, MUST refuse to replace an unrelated listener, and MUST start the
bundled backend invisibly when the port is unused. It MUST signal and wait for
graceful shutdown of an owned backend and MUST NOT stop a reused backend.

#### Scenario: Existing healthy service is reused

- **GIVEN** codex-lb is healthy on the selected port
- **WHEN** the native app opens and closes
- **THEN** the dashboard uses that service
- **AND** the service remains healthy with the same process after the app closes

#### Scenario: Bundled backend is owned

- **GIVEN** the selected port is unused
- **WHEN** the native app opens and closes
- **THEN** it starts the bundled backend with a private shutdown event
- **AND** closing the window causes the backend to complete graceful Uvicorn shutdown

### Requirement: XA LB icon identifies the running application

The native executable MUST embed a deterministic multi-resolution icon matching
the XA DevHub visual language with `LB` lettering. The large and small window
class icons, title bar, taskbar, and executable file MUST use that resource.

#### Scenario: Native application is running

- **WHEN** Windows displays the executable or its running window
- **THEN** the XA-style LB icon is visible instead of a generic application icon

### Requirement: Native release preserves codex-lb data and is verified

The release MUST use ordinary codex-lb data-directory resolution so existing
accounts, settings, usage history, and request statistics appear without import.
The build MUST assemble a one-directory release with the native host and bundled
backend, MUST exclude local auth/database/key files, and MUST fail unless an
isolated packaged self-test verifies health, readiness, dashboard HTML/assets,
statistics API, persistence initialization, and graceful shutdown.

#### Scenario: XA native build completes

- **WHEN** `python xa-app/build.py` reports success
- **THEN** `xa-app/release/Codex LB/Codex LB.exe` exists as a native PE
- **AND** the release contains its headless backend and required resources
- **AND** every packaged self-test check has passed
