# Codex LB native Windows application

This folder owns the complete open-source build for the XA Windows application. The visible `Codex LB.exe` is a native C++17 Win32/WebView2 host. It starts the existing codex-lb Python service without a console window, displays the React dashboard in a real application window, and closes only the backend process it started.

The owning behavior specification is [`../openspec/specs/windows-desktop/spec.md`](../openspec/specs/windows-desktop/spec.md).

## Build and run

From the repository root:

```powershell
python xa-app\build.py --run
```

The builder discovers the local Windows toolchain, builds and verifies every layer, then writes:

```text
xa-app\release\Codex LB\Codex LB.exe
```

Use `python xa-app\build.py` when you only want to build. Use `--full-tests` to add the complete upstream Python unit suite. `--no-pause` is useful for automation.

Required local tools are Python/uv, Bun, CMake, Visual Studio 2022 Build Tools with the C++ x64 workload, and the Microsoft Edge WebView2 Evergreen Runtime. The builder downloads only the pinned WebView2 SDK package recorded in `dependencies.lock.json` and verifies its SHA-256 before use.

## What runs

- `Codex LB.exe` is the native user-facing application with the LB window/taskbar icon.
- `backend\codex-lb-backend.exe` is the hidden packaged form of the upstream Python/FastAPI server.
- If a healthy codex-lb service is already listening on the selected port, the app reuses it and leaves it running when the window closes.
- Otherwise the app starts an owned backend, signals a graceful shutdown when the window closes, and uses a Windows Job Object only as a crash failsafe.
- An owned bundled backend disables the internal HTTP Responses session bridge and uses codex-lb's direct HTTP streaming/retry path. A reused service keeps its existing configuration.

The normal data directory is `%USERPROFILE%\.codex-lb`. It contains the application database, encryption key, logs, and WebView2 profile. The release never includes `auth.json`, `store.db`, or `encryption.key`.

## Accounts and historical data

Open the **Accounts** page and use **Import** to select each local Codex `auth.json`, or use **Add account** for a fresh OAuth login. Importing an auth file adds the account credentials and current quota state; it does not reconstruct old request logs that never passed through codex-lb.

Dashboard history is stored in `%USERPROFILE%\.codex-lb\store.db`. Leave the application running while Codex clients are configured to use `http://127.0.0.1:2455/backend-api/codex`; new requests and usage snapshots are then recorded automatically. Closing the native window gracefully stops its owned backend. Data remains on disk and is available the next time the application opens.

## Source layout

```text
xa-app/
  build.py                 reproducible build, release, and test entry point
  backend_entry.py         hidden Uvicorn wrapper and named-event shutdown
  backend.spec             PyInstaller backend recipe
  CMakeLists.txt           native x64 build
  dependencies.lock.json   pinned external build dependencies
  resources/               manifest, version info, generated multi-size icon
  src/main.cpp             Win32/WebView2 application and backend ownership
  tools/make_icon.ps1      deterministic XA-style LB icon generator
  tests/                    source and backend safety contracts
```

Generated `build`, `deps`, `release`, and `backups` directories are local build state rather than application source.
