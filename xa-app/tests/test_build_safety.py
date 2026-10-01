from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "build.py"
SPEC = importlib.util.spec_from_file_location("xa_native_build", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
native_build = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(native_build)


@pytest.mark.parametrize("busy", [False, True])
def test_safe_clean_directory_preserves_running_release(tmp_path: Path, monkeypatch, busy: bool) -> None:
    release = tmp_path / "release" / "Codex LB"
    release.mkdir(parents=True)
    marker = release / "keep.txt"
    marker.write_text("active release", encoding="utf-8")
    monkeypatch.setattr(native_build, "RELEASE_DIR", release)
    monkeypatch.setattr(native_build, "_running_output_processes", lambda path: [42] if busy else [])

    if busy:
        with pytest.raises(native_build.BuildError, match="running"):
            native_build._safe_clean_directory(release)
        assert marker.read_text(encoding="utf-8") == "active release"
    else:
        native_build._safe_clean_directory(release)
        assert not release.exists()


def test_running_output_processes_matches_exact_directory(tmp_path: Path, monkeypatch) -> None:
    release = tmp_path / "release" / "Codex LB"
    # Process paths still protect a partially deleted directory with no executable on disk.
    processes = [
        {"ProcessId": 42, "ExecutablePath": str(release / "backend" / "codex-lb-backend.exe")},
        {"ProcessId": 43, "ExecutablePath": str(release / "Codex LB.exe")},
        {"ProcessId": 44, "ExecutablePath": str(release.with_name("Codex LB staged other") / "Codex LB.exe")},
    ]
    monkeypatch.setattr(
        native_build.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess([], 0, stdout=json.dumps(processes), stderr=""),
    )

    assert native_build._running_output_processes(release) == [42, 43]


@pytest.mark.parametrize("stdout", ["[]", "not json", '[{"ProcessId": 42, "ExecutablePath": null}]'])
def test_running_output_processes_fails_closed_on_invalid_inspection(tmp_path: Path, monkeypatch, stdout: str) -> None:
    monkeypatch.setattr(
        native_build.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess([], 0, stdout=stdout, stderr=""),
    )

    if stdout == "[]":
        assert native_build._running_output_processes(tmp_path) == []
    else:
        with pytest.raises(native_build.BuildError, match="inspect"):
            native_build._running_output_processes(tmp_path)


def test_safe_clean_directory_retains_files_when_inspection_fails(tmp_path: Path, monkeypatch) -> None:
    release = tmp_path / "release"
    release.mkdir()
    marker = release / "keep.txt"
    marker.write_text("keep", encoding="utf-8")
    monkeypatch.setattr(native_build, "RELEASE_DIR", release)

    def fail_inspection(path: Path) -> list[int]:
        raise native_build.BuildError("Cannot inspect native processes")

    monkeypatch.setattr(native_build, "_running_output_processes", fail_inspection)
    with pytest.raises(native_build.BuildError, match="inspect"):
        native_build._safe_clean_directory(release)
    assert marker.read_text(encoding="utf-8") == "keep"


def test_running_output_processes_fails_closed_on_query_failure(tmp_path: Path, monkeypatch) -> None:
    def failed_query(*args, **kwargs):
        raise subprocess.CalledProcessError(1, "powershell.exe")

    monkeypatch.setattr(native_build.subprocess, "run", failed_query)
    with pytest.raises(native_build.BuildError, match="Cannot inspect"):
        native_build._running_output_processes(tmp_path)


def test_safe_clean_directory_refuses_unapproved_target(tmp_path: Path) -> None:
    protected = tmp_path / "protected"
    protected.mkdir()
    with pytest.raises(native_build.BuildError, match="unapproved"):
        native_build._safe_clean_directory(protected)
    assert protected.is_dir()


@pytest.mark.parametrize("busy", [False, True])
def test_assemble_release_uses_safe_destination(tmp_path: Path, monkeypatch, busy: bool) -> None:
    release_root = tmp_path / "release"
    release = release_root / "Codex LB"
    release.mkdir(parents=True)
    marker = release / "active.txt"
    marker.write_text("active release", encoding="utf-8")
    native = tmp_path / "Codex LB.exe"
    native.write_bytes(b"new native host")
    bundle = tmp_path / "backend-bundle"
    bundle.mkdir()
    (bundle / "codex-lb-backend.exe").write_bytes(b"new backend")
    monkeypatch.setattr(native_build, "RELEASE_ROOT", release_root)
    monkeypatch.setattr(native_build, "RELEASE_DIR", release)
    monkeypatch.setattr(native_build, "_running_output_processes", lambda path: [42] if busy else [])

    executable = native_build._assemble_release(native, bundle, "test-version")

    if busy:
        assert executable.parent.parent == release_root
        assert executable.parent.name.startswith("Codex LB staged ")
        assert marker.read_text(encoding="utf-8") == "active release"
    else:
        assert executable.parent == release
        assert not marker.exists()
    assert executable.read_bytes() == b"new native host"
    assert (executable.parent / "backend" / "codex-lb-backend.exe").read_bytes() == b"new backend"
    manifest = json.loads((executable.parent / "release-manifest.json").read_text(encoding="utf-8"))
    assert manifest["version"] == "test-version"
    assert manifest["sha256"]["Codex LB.exe"] == native_build._sha256(native)


@pytest.mark.parametrize("busy", [False, True])
def test_launch_verified_release_defers_while_release_is_running(tmp_path: Path, monkeypatch, busy: bool) -> None:
    launched = []
    monkeypatch.setattr(native_build, "_running_output_processes", lambda path: [42] if busy else [])
    monkeypatch.setattr(native_build, "_launch", launched.append)
    executable = tmp_path / "Codex LB.exe"

    native_build._launch_verified_release(executable)

    assert launched == ([] if busy else [executable])


def test_safe_remove_generated_child_removes_only_exact_child(tmp_path: Path) -> None:
    generated = tmp_path / "native-self-test-data"
    generated.mkdir()
    (generated / "report.json").write_text("{}", encoding="utf-8")

    native_build._safe_remove_generated_child(
        generated,
        parent=tmp_path,
        expected_name="native-self-test-data",
    )

    assert not generated.exists()


def test_safe_remove_generated_child_refuses_wrong_name(tmp_path: Path) -> None:
    protected = tmp_path / "protected"
    protected.mkdir()

    with pytest.raises(native_build.BuildError, match="Refusing"):
        native_build._safe_remove_generated_child(
            protected,
            parent=tmp_path,
            expected_name="native-self-test-data",
        )

    assert protected.is_dir()
