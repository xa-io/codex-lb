from __future__ import annotations

import json
from pathlib import Path

XA_APP = Path(__file__).resolve().parents[1]


def test_dependency_lock_pins_webview2_with_sha256() -> None:
    lock = json.loads((XA_APP / "dependencies.lock.json").read_text(encoding="utf-8"))
    webview = lock["webview2"]
    assert webview["version"] == "1.0.4078.44"
    assert len(webview["sha256"]) == 64
    int(webview["sha256"], 16)


def test_native_host_uses_owned_shutdown_event_and_webview2() -> None:
    source = (XA_APP / "src" / "main.cpp").read_text(encoding="utf-8")
    assert "CreateCoreWebView2EnvironmentWithOptions" in source
    assert "CreateEventW" in source
    assert "SetEvent" in source
    assert "JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE" in source
    assert "TerminateProcess(g_app.backendProcess" in source
    assert "backendReady.load()" in source
    assert source.count("g_app.backendReady = true") == 2
    assert "taskkill" not in source.casefold()


def test_native_host_uses_static_webview_loader_and_static_msvc_runtime() -> None:
    cmake = (XA_APP / "CMakeLists.txt").read_text(encoding="utf-8")
    assert "WebView2LoaderStatic.lib" in cmake
    assert 'MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>"' in cmake


def test_release_contract_excludes_local_auth_and_database_names() -> None:
    expected_exclusions = {"auth.json", "store.db", "encryption.key"}
    build_source = (XA_APP / "build.py").read_text(encoding="utf-8")
    assert all(name in build_source for name in expected_exclusions)
    assert "def _safe_remove_generated_child" in build_source
    assert "shutil.rmtree(package_dir)" not in build_source
    assert "shutil.rmtree(test_data)" not in build_source


def test_backend_spec_excludes_unused_legacy_database_drivers() -> None:
    spec = (XA_APP / "backend.spec").read_text(encoding="utf-8")
    assert '"MySQLdb"' in spec
    assert '"pysqlite2"' in spec
    assert '"sqlalchemy.dialects.sqlite.aiosqlite"' in spec
    assert '"sqlalchemy.dialects.postgresql.asyncpg"' in spec
    assert '"sqlalchemy.dialects.postgresql.psycopg"' in spec


def test_icon_generator_has_all_windows_icon_sizes_and_lb_letters() -> None:
    source = (XA_APP / "tools" / "make_icon.ps1").read_text(encoding="utf-8")
    assert "$sizes = 256, 128, 64, 48, 32, 24, 16" in source
    assert "DrawString('L'" in source
    assert "DrawString('B'" in source
