from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules


xa_app_dir = Path(SPECPATH)
repo_root = xa_app_dir.parent
hidden_imports = (
    collect_submodules("app")
    + collect_submodules("aiosqlite")
    + collect_submodules("sqlalchemy.dialects.sqlite")
    + [
        "sqlalchemy.dialects.sqlite.aiosqlite",
        "sqlalchemy.dialects.postgresql.asyncpg",
        "sqlalchemy.dialects.postgresql.psycopg",
    ]
)
datas = [
    (str(repo_root / "app" / "static"), "app/static"),
    (str(repo_root / "app" / "db" / "alembic"), "app/db/alembic"),
    (str(repo_root / "app" / "modules" / "oauth" / "templates"), "app/modules/oauth/templates"),
    (str(repo_root / "config"), "config"),
]

# PyInstaller's SQLAlchemy hook probes these legacy optional database drivers.
# Codex LB's required SQLite and PostgreSQL drivers are explicitly collected above.
analysis = Analysis(
    [str(xa_app_dir / "backend_entry.py")],
    pathex=[str(repo_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "MySQLdb",
        "PyQt5",
        "PyQt6",
        "PySide2",
        "PySide6",
        "pysqlite2",
        "tkinter",
        "webview",
    ],
    noarchive=False,
    optimize=0,
)
python_archive = PYZ(analysis.pure)

executable = EXE(
    python_archive,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="codex-lb-backend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch="x86_64",
    codesign_identity=None,
    entitlements_file=None,
)

bundle = COLLECT(
    executable,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="codex-lb-backend",
)
