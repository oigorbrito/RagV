"""Synthetic execution of the actual profile writer/bootstrap and Compose contracts."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
POWERSHELL = shutil.which("pwsh") or shutil.which("powershell")


@pytest.mark.skipif(not POWERSHELL, reason="PowerShell is required for Windows profile contracts")
@pytest.mark.parametrize("compose", [False, True], ids=["profile-lifecycle", "compose-receivers"])
def test_datajud_persistent_profile_lifecycle(tmp_path, compose):
    if compose and not shutil.which("docker"):
        pytest.skip("Docker Compose CLI is required; no daemon/provider call is made")
    result = subprocess.run(
        [POWERSHELL, "-NoProfile", "-NonInteractive", "-File",
         str(ROOT / "tests/datajud_persistence_contract.ps1"),
         "-Root", str(ROOT), "-Scratch", str(tmp_path),
         *(["-CheckCompose"] if compose else [])],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    record = json.loads(result.stdout.strip().splitlines()[-1])
    assert record["status"] == "pass"
    assert record["compose_checked"] is compose
    assert "synthetic-datajud-secret" not in result.stdout + result.stderr
