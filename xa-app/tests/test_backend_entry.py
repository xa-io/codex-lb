from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "backend_entry.py"
SPEC = importlib.util.spec_from_file_location("xa_backend_entry", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
backend_entry = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(backend_entry)


def test_parse_args_accepts_loopback() -> None:
    args = backend_entry._parse_args(
        ["--host", "127.0.0.1", "--port", "2455", "--shutdown-event", "Local\\test"]
    )
    assert args.host == "127.0.0.1"
    assert args.port == 2455


@pytest.mark.parametrize("host", ["0.0.0.0", "192.168.1.5", "example.com"])
def test_parse_args_rejects_non_loopback(host: str) -> None:
    with pytest.raises(SystemExit):
        backend_entry._parse_args(
            ["--host", host, "--port", "2455", "--shutdown-event", "Local\\test"]
        )


def test_redacting_stream_removes_sensitive_values(tmp_path: Path) -> None:
    log_path = tmp_path / "backend.log"
    with log_path.open("w", encoding="utf-8") as target:
        stream = backend_entry._RedactingStream(target)
        stream.write("token=abc password: xyz Authorization=secret Bearer qwerty\n")

    content = log_path.read_text(encoding="utf-8")
    assert "abc" not in content
    assert "xyz" not in content
    assert "qwerty" not in content
    assert content.count("[REDACTED]") >= 3
