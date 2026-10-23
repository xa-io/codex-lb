from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config.settings import Settings, warn_removed_settings

pytestmark = pytest.mark.unit


def test_images_host_can_be_selected_without_changing_renderer(monkeypatch):
    monkeypatch.setenv("CODEX_LB_IMAGES_HOST_MODEL", "gpt-6-sol")
    settings = Settings(_env_file=None, images_default_model="gpt-image-2.5-sunburst")
    assert settings.images_host_model == "gpt-6-sol"
    assert settings.images_default_model == "gpt-image-2.5-sunburst"
    assert warn_removed_settings({"CODEX_LB_IMAGES_HOST_MODEL": "gpt-6-sol"}) == []


@pytest.mark.parametrize("model", ["", " ", "gpt-6 astra"])
def test_images_host_rejects_empty_or_whitespace_model(model):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, images_host_model=model)
