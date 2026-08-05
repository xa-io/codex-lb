from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "build.py"
SPEC = importlib.util.spec_from_file_location("xa_native_build", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
native_build = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(native_build)


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
