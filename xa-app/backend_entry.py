############################################################################################################################
#
# CODEX LB BACKEND v1.01
#
# Runs the bundled codex-lb FastAPI service without opening a console window.
#
# This wrapper gives the native C++ desktop host a narrow, owned backend process. It writes redacted runtime logs,
# waits for the host's named shutdown event, and asks Uvicorn to complete its normal graceful shutdown sequence.
#
# Core Features:
# • Starts the existing upstream app.main FastAPI application
# • Binds only to the host and port explicitly supplied by the native launcher
# • Uses a named Windows event for graceful, ownership-safe shutdown
# • Redirects windowless output to the existing Codex LB data directory
# • Redacts token, password, authorization, secret, and API-key values from wrapper output
# • Records unhandled startup failures in a timestamped crash log
#
# Important Note: This is a hidden service component. Users launch Codex LB.exe, not this executable directly.
#
# Codex LB Backend v1.01
# Native desktop backend wrapper
# Created by: XA
# Last Updated: 2026-08-02 20:28:00
#
# ## Release Notes ##
#
# v1.01 - Made stream finalization safe after its target file closes.
# v1.00 - Added the owned, event-driven backend entry point for the native Windows application.
#
############################################################################################################################

from __future__ import annotations

import argparse
import ctypes
import io
import os
import re
import sys
import threading
import traceback
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import TextIO

_SYNCHRONIZE = 0x00100000
_INFINITE = 0xFFFFFFFF
_REDACTION_PATTERNS = (
    re.compile(r"(?i)(password|passwd|pwd|token|secret|api[_-]?key)(\s*[=:]\s*)([^\s,&]+)"),
    re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+"),
    re.compile(r"(?i)(authorization\s*[=:]\s*)(?!\s*bearer\b)([^,&]+)"),
)


class _RedactingStream(io.TextIOBase):
    """Line-oriented file stream that removes common credential values."""

    def __init__(self, target: TextIO) -> None:
        self._target = target
        self._lock = threading.Lock()

    @property
    def encoding(self) -> str:
        return "utf-8"

    def writable(self) -> bool:
        return True

    def isatty(self) -> bool:
        return False

    def write(self, value: str) -> int:
        redacted = value
        redacted = _REDACTION_PATTERNS[0].sub(r"\1\2[REDACTED]", redacted)
        redacted = _REDACTION_PATTERNS[1].sub(r"\1[REDACTED]", redacted)
        redacted = _REDACTION_PATTERNS[2].sub(r"\1[REDACTED]", redacted)
        with self._lock:
            written = self._target.write(redacted)
            self._target.flush()
        return written

    def flush(self) -> None:
        with self._lock:
            if not self._target.closed:
                self._target.flush()


def _data_directory() -> Path:
    configured = os.getenv("CODEX_LB_DATA_DIR", "").strip()
    return Path(configured) if configured else Path.home() / ".codex-lb"


def _configure_windowless_output() -> _RedactingStream:
    log_directory = _data_directory() / "logs"
    log_directory.mkdir(parents=True, exist_ok=True)
    log_path = log_directory / f"backend-{datetime.now().strftime('%Y-%m-%d')}.log"
    target = log_path.open("a", encoding="utf-8", buffering=1)
    stream = _RedactingStream(target)
    sys.stdout = stream
    sys.stderr = stream
    return stream


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the backend owned by the native Codex LB desktop host.")
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", required=True, type=int)
    parser.add_argument("--shutdown-event", required=True)
    args = parser.parse_args(argv)
    if args.host not in {"127.0.0.1", "localhost", "::1"}:
        parser.error("the bundled desktop backend may bind only to a loopback host")
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    return args


def _open_shutdown_event(name: str) -> int:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenEventW.argtypes = (ctypes.c_uint32, ctypes.c_int, ctypes.c_wchar_p)
    kernel32.OpenEventW.restype = ctypes.c_void_p
    handle = kernel32.OpenEventW(_SYNCHRONIZE, False, name)
    if not handle:
        error = ctypes.get_last_error()
        raise OSError(error, f"Could not open the native host shutdown event {name!r}")
    return int(handle)


def _close_handle(handle: int) -> None:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CloseHandle.argtypes = (ctypes.c_void_p,)
    kernel32.CloseHandle.restype = ctypes.c_int
    kernel32.CloseHandle(handle)


def _start_shutdown_waiter(handle: int, server: object) -> threading.Thread:
    def wait_for_host() -> None:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.WaitForSingleObject.argtypes = (ctypes.c_void_p, ctypes.c_uint32)
        kernel32.WaitForSingleObject.restype = ctypes.c_uint32
        kernel32.WaitForSingleObject(handle, _INFINITE)
        setattr(server, "should_exit", True)

    waiter = threading.Thread(target=wait_for_host, name="codex-lb-native-shutdown", daemon=True)
    waiter.start()
    return waiter


def main(argv: Sequence[str] | None = None) -> int:
    _configure_windowless_output()
    args = _parse_args(argv)
    os.environ["PORT"] = str(args.port)
    shutdown_handle = _open_shutdown_event(args.shutdown_event)
    try:
        import uvicorn

        from app.core.runtime_logging import build_log_config

        config = uvicorn.Config(
            "app.main:app",
            host=args.host,
            port=args.port,
            timeout_keep_alive=7200,
            ws_max_size=128 * 1024 * 1024,
            workers=1,
            proxy_headers=False,
            log_config=build_log_config(),
        )
        server = uvicorn.Server(config)
        _start_shutdown_waiter(shutdown_handle, server)
        server.run()
        return 0 if server.started else 1
    finally:
        _close_handle(shutdown_handle)


def _write_crash_log(error: BaseException) -> Path | None:
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_directory = _data_directory() / "logs"
    try:
        log_directory.mkdir(parents=True, exist_ok=True)
        crash_path = log_directory / f"crash_log_{timestamp}.log"
        crash_path.write_text(
            "\n".join(
                (
                    f"Crash Log - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                    f"Exception Type: {type(error).__name__}",
                    f"Exception Message: {error}",
                    "",
                    "Full Traceback:",
                    traceback.format_exc(),
                )
            ),
            encoding="utf-8",
        )
        return crash_path
    except Exception:
        return None


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except BaseException as exc:
        print(f"[CRITICAL ERROR] {type(exc).__name__}: {exc}", file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr)
        crash_log = _write_crash_log(exc)
        if crash_log is not None:
            print(f"[CRASH LOG SAVED] {crash_log}", file=sys.stderr)
        raise SystemExit(1) from exc
