############################################################################################################################
#
# CODEX LB NATIVE BUILDER v1.04
#
# Builds, verifies, and optionally runs the native XA Codex LB Windows application.
#
# This is the single developer entry point for the xa-app source tree. It builds the React dashboard and freezes the
# existing Python service as a hidden backend. It also compiles the C++ WebView2 host, assembles a clean release, and
# performs an isolated native end-to-end self-test before reporting success.
#
# Core Features:
# • Discovers uv, Bun, CMake, and Visual Studio Build Tools from PATH and common Windows locations
# • Pins and verifies the Microsoft WebView2 SDK download by SHA-256
# • Regenerates the XA-style multi-resolution LB icon from open PowerShell source
# • Produces a native C++ Codex LB.exe and a windowless bundled backend
# • Refuses unsafe cleanup targets and snapshots source inputs before rebuilding
# • Verifies health, readiness, dashboard assets, statistics API, persistence, and graceful shutdown
# • Rejects auth.json, store.db, and encryption.key from the assembled release
# • Writes timestamped crash logs without terminating unrelated processes
#
# Important Note: The release self-test uses an isolated temporary data directory and never imports local credentials.
#
# Codex LB Native Builder v1.04
# Native Windows build and verification orchestrator
# Created by: XA
# Last Updated: 2026-09-30
#
# ## Release Notes ##
#
# v1.04 - Preserved running releases, staged new output safely, and deferred launch while a release is active.
# v1.03 - Guarded dependency and self-test child-directory cleanup with exact parent and name checks.
# v1.02 - Preserved and displayed the native JSON self-test report when a packaged runtime check fails.
# v1.01 - Tightened builder formatting and diagnostics before the first production build.
# v1.00 - Added reproducible native C++ host, bundled backend, release assembly, and end-to-end verification.
#
############################################################################################################################

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import tomllib
import traceback
import urllib.request
import zipfile
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

XA_APP_DIR = Path(__file__).resolve().parent
REPO_ROOT = XA_APP_DIR.parent
BUILD_DIR = XA_APP_DIR / "build"
DEPENDENCIES_DIR = XA_APP_DIR / "deps"
RELEASE_ROOT = XA_APP_DIR / "release"
RELEASE_DIR = RELEASE_ROOT / "Codex LB"
BACKUPS_DIR = XA_APP_DIR / "backups"
LOCK_FILE = XA_APP_DIR / "dependencies.lock.json"
PROHIBITED_RELEASE_NAMES = {"auth.json", "store.db", "encryption.key"}


class BuildError(RuntimeError):
    """Expected build failure with a user-actionable message."""


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build and verify the native Codex LB Windows application.")
    parser.add_argument("--run", action="store_true", help="Open Codex LB.exe after the verified build finishes.")
    parser.add_argument(
        "--full-tests",
        action="store_true",
        help="Run the upstream Python unit suite in addition to xa-app contract tests and the native self-test.",
    )
    parser.add_argument("--no-pause", action="store_true", help="Do not wait for Enter when launched in a terminal.")
    return parser.parse_args(argv)


def _banner(title: str) -> None:
    print()
    print("=" * 80)
    print(title)
    print("=" * 80)


def _run(
    command: Sequence[str | os.PathLike[str]],
    *,
    cwd: Path = REPO_ROOT,
    timeout: int | None = None,
    capture: bool = False,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    rendered = " ".join(str(part) for part in command)
    print(f"> {rendered}")
    result = subprocess.run(
        [str(part) for part in command],
        cwd=cwd,
        check=False,
        text=True,
        capture_output=capture,
        timeout=timeout,
    )
    if check and result.returncode != 0:
        detail = ""
        if capture:
            detail = f"\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        raise BuildError(f"Command failed with exit code {result.returncode}: {rendered}{detail}")
    return result


def _find_executable(name: str, candidates: Sequence[Path]) -> Path:
    discovered = shutil.which(name)
    if discovered:
        return Path(discovered).resolve()
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    locations = "\n".join(f"  - {candidate}" for candidate in candidates)
    raise BuildError(f"Required tool {name!r} was not found. Checked PATH and:\n{locations}")


def _toolchain() -> dict[str, Path]:
    local_app_data = Path(os.getenv("LOCALAPPDATA", ""))
    roaming_app_data = Path(os.getenv("APPDATA", ""))
    program_files = Path(os.getenv("ProgramFiles", r"C:\Program Files"))
    program_files_x86 = Path(os.getenv("ProgramFiles(x86)", r"C:\Program Files (x86)"))
    uv = _find_executable(
        "uv.exe",
        (
            Path.home() / ".local" / "bin" / "uv.exe",
            local_app_data / "Programs" / "uv" / "uv.exe",
        ),
    )
    bun = _find_executable(
        "bun.cmd",
        (
            roaming_app_data / "npm" / "bun.cmd",
            Path.home() / ".bun" / "bin" / "bun.exe",
        ),
    )
    cmake = _find_executable(
        "cmake.exe",
        (
            program_files / "CMake" / "bin" / "cmake.exe",
            program_files_x86 / "CMake" / "bin" / "cmake.exe",
        ),
    )
    powershell = _find_executable(
        "powershell.exe",
        (
            Path(os.environ.get("SystemRoot", r"C:\Windows"))
            / "System32"
            / "WindowsPowerShell"
            / "v1.0"
            / "powershell.exe",
        ),
    )
    vswhere = _find_executable(
        "vswhere.exe",
        (
            program_files_x86 / "Microsoft Visual Studio" / "Installer" / "vswhere.exe",
            program_files / "Microsoft Visual Studio" / "Installer" / "vswhere.exe",
        ),
    )
    return {"uv": uv, "bun": bun, "cmake": cmake, "powershell": powershell, "vswhere": vswhere}


def _verify_visual_studio(vswhere: Path) -> Path:
    result = _run(
        (
            vswhere,
            "-latest",
            "-products",
            "*",
            "-requires",
            "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
            "-property",
            "installationPath",
        ),
        capture=True,
    )
    install_path = Path(result.stdout.strip())
    if not install_path.is_dir():
        raise BuildError("Visual Studio 2022 Build Tools with the C++ x64 workload are required.")
    return install_path


def _running_output_processes(directory: Path) -> list[int]:
    powershell = _find_executable(
        "powershell.exe",
        (Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32/WindowsPowerShell/v1.0/powershell.exe",),
    )
    script = (
        "$ErrorActionPreference = 'Stop'; "
        "[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false); "
        "$items = @(Get-CimInstance Win32_Process -Filter "
        "\"Name = 'Codex LB.exe' OR Name = 'codex-lb-backend.exe'\" "
        "| Select-Object ProcessId,ExecutablePath); "
        "ConvertTo-Json -InputObject $items -Compress"
    )
    try:
        result = subprocess.run(
            [str(powershell), "-NoProfile", "-NonInteractive", "-Command", script],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        records = json.loads(result.stdout)
        if not isinstance(records, list):
            raise ValueError("Process inspection did not return an array")
        target = directory.resolve()
        running: list[int] = []
        for record in records:
            if not isinstance(record, dict):
                raise ValueError("Invalid process inspection record")
            executable = record.get("ExecutablePath")
            pid = record.get("ProcessId")
            if not isinstance(executable, str) or not executable or type(pid) is not int:
                raise ValueError("A native process could not be identified")
            if Path(executable).resolve().is_relative_to(target):
                running.append(pid)
        return running
    except (OSError, subprocess.SubprocessError, ValueError) as error:
        raise BuildError(f"Cannot inspect running native processes; output files were not cleaned: {error}") from error


def _safe_clean_directory(path: Path) -> None:
    resolved = path.resolve()
    allowed = {
        BUILD_DIR.resolve(),
        RELEASE_DIR.resolve(),
    }
    if resolved not in allowed:
        raise BuildError(f"Refusing to clean an unapproved path: {resolved}")
    if resolved.exists():
        running = _running_output_processes(resolved)
        if running:
            raise BuildError(f"Refusing to clean {resolved}: native processes are running (PIDs {running}).")
        print(f"Cleaning {resolved}")
        shutil.rmtree(resolved)


def _safe_remove_generated_child(path: Path, *, parent: Path, expected_name: str) -> None:
    resolved = path.resolve()
    resolved_parent = parent.resolve()
    if resolved.parent != resolved_parent or resolved.name != expected_name:
        raise BuildError(f"Refusing to remove an unexpected generated directory: {resolved}")
    if resolved.exists():
        shutil.rmtree(resolved)


def _snapshot_sources() -> Path:
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    snapshot = BACKUPS_DIR / f"source - {timestamp}"
    snapshot.mkdir(parents=True, exist_ok=False)
    names = (
        "backend.spec",
        "backend_entry.py",
        "build.py",
        "CMakeLists.txt",
        "dependencies.lock.json",
        "README.md",
    )
    for name in names:
        source = XA_APP_DIR / name
        if source.exists():
            shutil.copy2(source, snapshot / name)
    for directory in ("include", "resources", "src", "tests", "tools"):
        source = XA_APP_DIR / directory
        if source.is_dir():
            shutil.copytree(source, snapshot / directory)
    print(f"Source snapshot: {snapshot}")
    return snapshot


def _load_dependency_lock() -> dict[str, object]:
    try:
        value = json.loads(LOCK_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BuildError(f"Could not read {LOCK_FILE}: {exc}") from exc
    if not isinstance(value, dict):
        raise BuildError(f"{LOCK_FILE} must contain a JSON object.")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _download_webview2(lock: dict[str, object]) -> Path:
    webview = lock.get("webview2")
    if not isinstance(webview, dict):
        raise BuildError("dependencies.lock.json is missing the webview2 object.")
    version = str(webview.get("version", ""))
    url = str(webview.get("url", ""))
    expected_hash = str(webview.get("sha256", "")).upper()
    if not version or not url or len(expected_hash) != 64:
        raise BuildError("The WebView2 dependency lock is incomplete.")
    package_dir = DEPENDENCIES_DIR / f"Microsoft.Web.WebView2.{version}"
    header = package_dir / "build" / "native" / "include" / "WebView2.h"
    static_loader = package_dir / "build" / "native" / "x64" / "WebView2LoaderStatic.lib"
    if header.is_file() and static_loader.is_file():
        return package_dir

    DEPENDENCIES_DIR.mkdir(parents=True, exist_ok=True)
    archive = DEPENDENCIES_DIR / f"Microsoft.Web.WebView2.{version}.nupkg"
    if not archive.is_file() or _sha256(archive) != expected_hash:
        print(f"Downloading pinned WebView2 SDK {version}...")
        with urllib.request.urlopen(url, timeout=90) as response, archive.open("wb") as target:
            shutil.copyfileobj(response, target)
    actual_hash = _sha256(archive)
    if actual_hash != expected_hash:
        raise BuildError(f"WebView2 SDK SHA-256 mismatch. Expected {expected_hash}, received {actual_hash}.")
    _safe_remove_generated_child(
        package_dir,
        parent=DEPENDENCIES_DIR,
        expected_name=f"Microsoft.Web.WebView2.{version}",
    )
    with zipfile.ZipFile(archive) as package:
        package.extractall(package_dir)
    if not header.is_file() or not static_loader.is_file():
        raise BuildError("The verified WebView2 SDK package did not contain the expected native x64 files.")
    return package_dir


def _project_version() -> str:
    with (REPO_ROOT / "pyproject.toml").open("rb") as stream:
        project = tomllib.load(stream).get("project", {})
    version = project.get("version") if isinstance(project, dict) else None
    if not isinstance(version, str) or not version:
        raise BuildError("pyproject.toml does not contain a project version.")
    return version


def _prepare_python_and_frontend(tools: dict[str, Path], lock: dict[str, object]) -> Path:
    _banner("Preparing Python and dashboard dependencies")
    _run((tools["uv"], "sync", "--dev", "--frozen", "--no-install-project", "--inexact"))
    venv_python = REPO_ROOT / ".venv" / "Scripts" / "python.exe"
    if not venv_python.is_file():
        raise BuildError(f"uv did not create the expected interpreter: {venv_python}")
    pyinstaller = lock.get("pyinstaller")
    if not isinstance(pyinstaller, dict) or not pyinstaller.get("version"):
        raise BuildError("dependencies.lock.json is missing the PyInstaller version.")
    _run(
        (
            tools["uv"],
            "pip",
            "install",
            "--python",
            venv_python,
            f"pyinstaller=={pyinstaller['version']}",
        )
    )
    _run((tools["bun"], "install", "--frozen-lockfile"), cwd=REPO_ROOT / "frontend")
    _run((tools["bun"], "run", "build"), cwd=REPO_ROOT / "frontend")
    index = REPO_ROOT / "app" / "static" / "index.html"
    if not index.is_file():
        raise BuildError("The dashboard build did not produce app/static/index.html.")
    return venv_python


def _generate_icon(tools: dict[str, Path]) -> None:
    _banner("Generating XA-style application icon")
    _run(
        (
            tools["powershell"],
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            XA_APP_DIR / "tools" / "make_icon.ps1",
        )
    )
    icon = XA_APP_DIR / "resources" / "codex-lb.ico"
    if not icon.is_file() or icon.stat().st_size < 1024:
        raise BuildError("The icon generator did not produce a valid multi-resolution icon.")


def _build_backend(venv_python: Path) -> Path:
    _banner("Bundling the hidden codex-lb backend")
    backend_dist = BUILD_DIR / "backend-dist"
    backend_work = BUILD_DIR / "backend-work"
    _run(
        (
            venv_python,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--distpath",
            backend_dist,
            "--workpath",
            backend_work,
            XA_APP_DIR / "backend.spec",
        ),
        timeout=900,
    )
    bundle = backend_dist / "codex-lb-backend"
    executable = bundle / "codex-lb-backend.exe"
    if not executable.is_file():
        raise BuildError(f"PyInstaller did not produce {executable}")
    return bundle


def _build_native_host(tools: dict[str, Path], webview_sdk: Path) -> Path:
    _banner("Compiling native C++ Windows host")
    native_build = BUILD_DIR / "native"
    _run(
        (
            tools["cmake"],
            "-S",
            XA_APP_DIR,
            "-B",
            native_build,
            "-G",
            "Visual Studio 17 2022",
            "-A",
            "x64",
            f"-DWEBVIEW2_SDK_ROOT={webview_sdk}",
        )
    )
    _run((tools["cmake"], "--build", native_build, "--config", "Release", "--parallel"), timeout=600)
    executable = native_build / "Release" / "Codex LB.exe"
    if not executable.is_file():
        raise BuildError(f"CMake did not produce {executable}")
    return executable


def _assemble_release(native_executable: Path, backend_bundle: Path, version: str) -> Path:
    _banner("Assembling release")
    release_dir = RELEASE_DIR
    if _running_output_processes(RELEASE_DIR):
        release_dir = RELEASE_ROOT / f"Codex LB staged {datetime.now():%Y%m%d-%H%M%S-%f}"
        print(f"Keeping the running release intact; staging to {release_dir}")
    else:
        _safe_clean_directory(RELEASE_DIR)
    release_dir.mkdir(parents=True, exist_ok=False)
    shutil.copy2(native_executable, release_dir / "Codex LB.exe")
    shutil.copytree(backend_bundle, release_dir / "backend")

    manifest = {
        "product": "Codex LB",
        "version": version,
        "architecture": "x64",
        "entrypoint": "Codex LB.exe",
        "backend": "backend/codex-lb-backend.exe",
        "built_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "sha256": {
            "Codex LB.exe": _sha256(release_dir / "Codex LB.exe"),
            "backend/codex-lb-backend.exe": _sha256(release_dir / "backend" / "codex-lb-backend.exe"),
        },
    }
    (release_dir / "release-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    _verify_release_contents(release_dir)
    return release_dir / "Codex LB.exe"


def _verify_release_contents(release_dir: Path) -> None:
    found = [path for path in release_dir.rglob("*") if path.name.casefold() in PROHIBITED_RELEASE_NAMES]
    if found:
        rendered = "\n".join(f"  - {path}" for path in found)
        raise BuildError(f"Credential or local data files were found in the release:\n{rendered}")
    if not (release_dir / "Codex LB.exe").is_file():
        raise BuildError("The native release entry point is missing.")
    if not (release_dir / "backend" / "codex-lb-backend.exe").is_file():
        raise BuildError("The bundled backend entry point is missing.")


def _free_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _run_contract_tests(venv_python: Path, full_tests: bool) -> None:
    _banner("Running source contract tests")
    _run((venv_python, "-m", "pytest", "-q", XA_APP_DIR / "tests"), timeout=300)
    if full_tests:
        _banner("Running upstream Python unit tests")
        _run((venv_python, "-m", "pytest", "-q", REPO_ROOT / "tests" / "unit"), timeout=1800)


def _run_native_self_test(executable: Path) -> Path:
    _banner("Running isolated native release self-test")
    test_data = BUILD_DIR / "native-self-test-data"
    _safe_remove_generated_child(
        test_data,
        parent=BUILD_DIR,
        expected_name="native-self-test-data",
    )
    test_data.mkdir(parents=True)
    port = _free_loopback_port()
    result = _run(
        (executable, "--self-test", "--port", str(port), "--data-dir", test_data),
        timeout=240,
        capture=True,
        check=False,
    )
    report_path = test_data / "native-self-test.json"
    if not report_path.is_file():
        raise BuildError(
            f"The native self-test exited without writing {report_path}.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if result.returncode != 0 or report.get("passed") is not True:
        raise BuildError(f"The native release self-test failed:\n{json.dumps(report, indent=2)}")
    print(json.dumps(report, indent=2))
    return report_path


def _launch(executable: Path) -> None:
    _banner("Opening Codex LB")
    subprocess.Popen(
        [str(executable)],
        cwd=executable.parent,
        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
        close_fds=True,
    )
    print(f"Launched: {executable}")


def _launch_verified_release(executable: Path) -> None:
    if _running_output_processes(RELEASE_ROOT):
        print(f"Launch deferred while another release is running. Open this after closing the active app: {executable}")
        return
    _launch(executable)


def build(*, run_after: bool, full_tests: bool) -> Path:
    os.chdir(REPO_ROOT)
    _banner("Codex LB native Windows build")
    print(f"Repository: {REPO_ROOT}")
    print(f"XA app:     {XA_APP_DIR}")
    _snapshot_sources()
    tools = _toolchain()
    visual_studio = _verify_visual_studio(tools["vswhere"])
    print(f"Visual Studio: {visual_studio}")
    lock = _load_dependency_lock()
    version = _project_version()
    _safe_clean_directory(BUILD_DIR)
    BUILD_DIR.mkdir(parents=True)
    webview_sdk = _download_webview2(lock)
    venv_python = _prepare_python_and_frontend(tools, lock)
    _generate_icon(tools)
    _run_contract_tests(venv_python, full_tests)
    backend_bundle = _build_backend(venv_python)
    native_executable = _build_native_host(tools, webview_sdk)
    release_executable = _assemble_release(native_executable, backend_bundle, version)
    self_test_report = _run_native_self_test(release_executable)

    _banner("BUILD SUCCESSFUL")
    print(f"Application: {release_executable}")
    print(f"Backend:     {release_executable.parent / 'backend' / 'codex-lb-backend.exe'}")
    print(f"Self-test:   {self_test_report}")
    print("Data:        %USERPROFILE%\\.codex-lb")
    print("The visible application is Codex LB.exe; the backend has no window by design.")
    if run_after:
        _launch_verified_release(release_executable)
    return release_executable


def _write_crash_log(error: BaseException) -> Path | None:
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    crash_path = XA_APP_DIR / f"crash_log_{timestamp}.log"
    details = "\n".join(
        (
            f"Crash Log - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Exception Type: {type(error).__name__}",
            f"Exception Message: {error}",
            "",
            "Full Traceback:",
            traceback.format_exc(),
        )
    )
    try:
        crash_path.write_text(details, encoding="utf-8")
        return crash_path
    except OSError:
        return None


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    build(run_after=args.run, full_tests=args.full_tests)
    if not args.no_pause and sys.stdin.isatty():
        input("\nPress Enter to close...")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except BaseException as exc:
        print()
        print("=" * 80)
        print("BUILD FAILED")
        print("=" * 80)
        print(f"{type(exc).__name__}: {exc}")
        print(traceback.format_exc())
        crash_log = _write_crash_log(exc)
        if crash_log is not None:
            print(f"Crash log: {crash_log}")
        if "--no-pause" not in sys.argv and sys.stdin.isatty():
            input("\nPress Enter to close...")
        raise SystemExit(1) from exc
