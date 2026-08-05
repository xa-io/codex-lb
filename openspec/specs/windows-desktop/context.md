# Windows desktop context

## Purpose

The upstream codex-lb product is a FastAPI service with a React dashboard. The XA fork adds an operator-friendly Windows application without replacing either layer: a small native C++ host owns the visible window while the existing Python service remains the backend.

## Decisions

- The visible `Codex LB.exe` is C++17/Win32 and embeds Microsoft Edge WebView2.
- The WebView2 SDK is build-time pinned and SHA-256 verified. The installed Evergreen WebView2 Runtime supplies the browser engine at runtime.
- The native host links the WebView2 loader and Microsoft C++ runtime statically.
- The hidden backend is a one-directory PyInstaller bundle of the existing `app.main` service and its static assets, migrations, OAuth template, and quota registry.
- Port ownership is identity-aware. A listener is reusable only when `/health` returns the codex-lb body and `X-App-Version` header.
- An owned backend receives a private named Windows shutdown event. A Job Object is a crash failsafe; it is never applied to a reused service.
- Normal data remains in `%USERPROFILE%\.codex-lb`. Build and self-test data is isolated under `xa-app/build`.

## Historical data and account imports

Opening the native application does not create a second data store. Existing accounts, settings, request logs, and usage history appear automatically when the ordinary `%USERPROFILE%\.codex-lb\store.db` exists.

Importing `%USERPROFILE%\.codex\auth.json` from the dashboard Accounts page adds an account and enables current quota refreshes. It cannot reconstruct requests that were made before the client routed through codex-lb. New history accumulates while a Codex client uses `http://127.0.0.1:2455/backend-api/codex`.

## Failure modes

- If port 2455 belongs to an unrelated listener, the window shows an actionable error and does not terminate that process.
- If the owned backend exits or misses its readiness deadline, the window remains open with log guidance.
- If WebView2 is unavailable, the window explains that the Evergreen Runtime is required.
- If the window closes during owned startup or operation, it signals graceful shutdown, waits, and terminates only its exact child as a bounded fallback.
- If an existing healthy codex-lb service was reused, closing the window leaves that service running.

## Concrete example

An operator already has codex-lb on port 2455 with 410 request rows in `%USERPROFILE%\.codex-lb\store.db`. Opening `Codex LB.exe` identifies and reuses that service, then renders those same dashboard totals in the native window. Closing the window exits only the C++ process; the original server PID and its data remain unchanged.
