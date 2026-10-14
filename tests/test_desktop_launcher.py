"""No GUI or Docker needed for desktop launcher contract tests."""
import importlib.util
from pathlib import Path
from unittest.mock import patch

import pytest

SPEC = importlib.util.spec_from_file_location(
    "desktop_launcher", Path(__file__).resolve().parents[1] / "scripts" / "desktop_launcher.py"
)
launcher = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(launcher)


@pytest.mark.parametrize("value", [
    "https://127.0.0.1:8000", "http://example.com:8000",
    "http://127.0.0.1:8000/other", "http://127.0.0.1:8000/?x=1",
    "http://user:pass@127.0.0.1:8000", "http://127.0.0.1",
])
def test_reject_nonlocal_or_ambiguous_origin(value):
    with pytest.raises(ValueError):
        launcher.local_origin(value)


def test_accept_loopback_origin():
    assert launcher.local_origin("http://127.0.0.1:8000/") == "http://127.0.0.1:8000"


def test_no_gui_launch_when_api_unavailable():
    with patch.object(launcher, "is_ready", return_value=False):
        assert launcher.main([]) == 1
