# Protect the running native release during builds

## Why

Release assembly currently deletes the installed release directory even when its native host or backend is running. Windows refuses to delete loaded binaries, so assembly can fail after partially removing dependencies from an authenticated session.

## What Changes

- Check the exact executable paths of running XA native hosts and backends before cleaning an approved build or release directory.
- Assemble a uniquely named sibling release when the default release is running, retaining the active process and its files.
- Verify and report the actual assembled release directory, and defer `--run` while another release is active.

## Impact

- Affected spec: windows-desktop.
- Affected code: xa-app/build.py and build-safety tests.
- Recovery can assemble the already compiled native and backend outputs without repeating compilation or terminating the active session.
