# Running release lock recovery

On 2026-09-30, the user build reached release assembly and failed while deleting `backend/_internal/aiohttp/_websocket/mask.cp314-win_amd64.pyd`. The native host and its owned backend were still running from the default release directory, and health/readiness checks continued returning HTTP 200. The compilation outputs were already available under `xa-app/build/`.

The builder will inspect executable paths without reading credentials or process command lines. Cleanup must fail before deletion when a native host or backend runs from the approved target, including when the original executable file has already been partially removed. Failed or incomplete process inspection must stop cleanup rather than assume the target is unused.

If the default release is running, assembly writes to a new `xa-app/release/Codex LB staged <timestamp>/` sibling and verifies that directory. It does not close or restart the active host/backend. The isolated native self-test uses its own data directory and loopback port. An automatic launch is deferred until the operator closes the existing release, because another host on the default port would reuse the old backend.

The earlier failed cleanup may already have removed some unlocked files from the old release. This repair leaves the running folder untouched and provides a complete separately verified release for the operator's eventual switch.
