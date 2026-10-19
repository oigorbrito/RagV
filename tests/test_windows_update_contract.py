import os
from pathlib import Path
import shutil
import subprocess
import time

import pytest


ROOT = Path(__file__).resolve().parents[1]


def test_update_verifier_fails_closed_on_signature_and_hash() -> None:
    text = (ROOT / "scripts/verify_windows_update.ps1").read_text(encoding="utf-8-sig")
    assert "Get-AuthenticodeSignature" in text
    assert "Status -ne 'Valid'" in text
    assert "Get-FileHash" in text
    assert "hash do instalador não corresponde" in text
    assert "version" in text and "publisher" in text
    assert "Atualização rejeitada" in text


def test_update_verifier_does_not_apply_or_touch_docker() -> None:
    text = (ROOT / "scripts/verify_windows_update.ps1").read_text(encoding="utf-8-sig")
    assert "Start-Process" not in text
    assert "docker" not in text.lower()
    assert "Copy-Item" not in text
    assert "Remove-Item" not in text


def test_inno_installer_is_the_current_artifact_boundary() -> None:
    text = (ROOT / "packaging/windows/RagVDesktop.iss").read_text(encoding="utf-8-sig")
    assert "OutputBaseFilename" in text
    assert "RagVDesktop.exe" in text
    assert "ProjectDir" in text
    assert "PrivilegesRequired=lowest" in text


def test_compose_updater_serializes_calls_for_the_same_checkout() -> None:
    text = (ROOT / "scripts/update-ragv-desktop.ps1").read_text(encoding="utf-8-sig")
    assert "System.Threading.Mutex" in text
    assert "WaitOne(0)" in text
    assert "AbandonedMutexException" in text
    assert "ReleaseMutex()" in text
    assert text.index("WaitOne(0)") < text.index("docker info")
    assert text.index("Get-FileHash -LiteralPath $backupFullPath") < text.index("docker compose build")
    assert "Checksum do backup não confere" in text


@pytest.mark.skipif(os.name != "nt", reason="Requires Windows named-mutex semantics and cmd shim")
def test_concurrent_compose_updater_is_rejected_before_docker(tmp_path: Path) -> None:
    powershell = shutil.which("powershell.exe")
    if not powershell:
        pytest.skip("Windows PowerShell 5.1 unavailable")
    shim_dir = tmp_path / "mock tools"
    shim_dir.mkdir()
    log = tmp_path / "docker-calls.log"
    mock_script = tmp_path / "mock-docker.ps1"
    mock_script.write_text(
        "$DockerArgs = $args\n"
        "Add-Content -LiteralPath $env:RAGV_DOCKER_LOG -Value ($DockerArgs -join ' ')\n"
        "if ($DockerArgs[0] -eq 'info') { Start-Sleep -Seconds 3 }\n"
        "if ($DockerArgs.Count -ge 2 -and $DockerArgs[0] -eq 'compose' -and $DockerArgs[1] -eq 'run' -and $env:RAGV_MOCK_BACKUP_MODE -eq 'valid') {\n"
        "  $p=$env:RAGV_MOCK_BACKUP_FILE; [IO.File]::WriteAllText($p,'synthetic-backup'); $h=(Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLowerInvariant(); [IO.File]::WriteAllText($p+'.sha256', $h+'  '+[IO.Path]::GetFileName($p))\n"
        "}\n"
        "exit 0\n",
        encoding="utf-8",
    )
    wrapper = (shim_dir / "docker.cmd")
    wrapper.write_text(
        '@echo off\r\n'
        '"%WINDIR%\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -File "%RAGV_MOCK_DOCKER_SCRIPT%" %*\r\n'
        'exit /b %ERRORLEVEL%\r\n',
        encoding="ascii",
    )
    env = os.environ.copy()
    env["PATH"] = str(shim_dir) + os.pathsep + env.get("PATH", "")
    env["RAGV_DOCKER_LOG"] = str(log)
    env["RAGV_MOCK_DOCKER_SCRIPT"] = str(mock_script)
    env["RAGV_MOCK_BACKUP_MODE"] = "valid"
    script = ROOT / "scripts/update-ragv-desktop.ps1"
    first_backup = tmp_path / "first backup.dump"
    second_backup = tmp_path / "second backup.dump"

    def command(backup: Path) -> list[str]:
        return [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script), "-BackupPath", str(backup)]

    env["RAGV_MOCK_BACKUP_FILE"] = str(first_backup)
    first = subprocess.Popen(command(first_backup), env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if log.exists() and "info" in log.read_text(encoding="utf-8", errors="replace").lower():
            break
        if first.poll() is not None:
            stdout, stderr = first.communicate()
            pytest.fail(f"First mocked update stopped before Docker: {stdout} {stderr}")
        time.sleep(0.05)
    else:
        first.kill()
        pytest.fail("First mocked update never reached the docker shim")

    second = subprocess.run(command(second_backup), env=env, text=True, capture_output=True, timeout=15)
    stdout, stderr = first.communicate(timeout=30)
    assert second.returncode != 0
    assert "em andamento" in (second.stdout + second.stderr)
    assert first.returncode == 0, stdout + stderr
    calls = log.read_text(encoding="utf-8", errors="replace").splitlines()
    assert sum(line.strip().lower() == "info" for line in calls) == 1
    assert sum(line.lower().startswith("compose build") for line in calls) == 1


@pytest.mark.skipif(os.name != "nt", reason="Uses PowerShell and a docker shim")
@pytest.mark.parametrize("backup_mode", ["missing", "bad-checksum"])
def test_updater_cancels_before_build_when_backup_is_invalid(tmp_path: Path, backup_mode: str) -> None:
    powershell = shutil.which("powershell.exe")
    if not powershell:
        pytest.skip("Windows PowerShell 5.1 unavailable")
    shim_dir = tmp_path / "mock tools"
    shim_dir.mkdir()
    log = tmp_path / "docker-calls.log"
    mock_script = tmp_path / "mock-docker.ps1"
    mock_script.write_text(
        "$DockerArgs = $args\n"
        "Add-Content -LiteralPath $env:RAGV_DOCKER_LOG -Value ($DockerArgs -join ' ')\n"
        "if ($DockerArgs.Count -ge 2 -and $DockerArgs[0] -eq 'compose' -and $DockerArgs[1] -eq 'run' -and $env:RAGV_MOCK_BACKUP_MODE -eq 'bad-checksum') { $p=$env:RAGV_MOCK_BACKUP_FILE; [IO.File]::WriteAllText($p,'synthetic-backup'); [IO.File]::WriteAllText($p+'.sha256', ('0'*64)+'  '+[IO.Path]::GetFileName($p)) }\n"
        "exit 0\n",
        encoding="utf-8",
    )
    (shim_dir / "docker.cmd").write_text(
        '@echo off\r\n'
        '"%WINDIR%\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -File "%RAGV_MOCK_DOCKER_SCRIPT%" %*\r\n'
        'exit /b %ERRORLEVEL%\r\n',
        encoding="ascii",
    )
    env = os.environ.copy()
    env["PATH"] = str(shim_dir) + os.pathsep + env.get("PATH", "")
    env["RAGV_DOCKER_LOG"] = str(log)
    env["RAGV_MOCK_DOCKER_SCRIPT"] = str(mock_script)
    env["RAGV_MOCK_BACKUP_MODE"] = backup_mode
    backup = tmp_path / "synthetic backup.dump"
    env["RAGV_MOCK_BACKUP_FILE"] = str(backup)
    result = subprocess.run(
        [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "scripts/update-ragv-desktop.ps1"), "-BackupPath", str(backup)],
        env=env,
        text=True,
        capture_output=True,
        timeout=20,
    )
    assert result.returncode != 0
    expected_error = "Checksum do backup" if backup_mode == "bad-checksum" else "Backup validado ou checksum ausente"
    assert expected_error in (result.stdout + result.stderr)
    calls = log.read_text(encoding="utf-8", errors="replace").splitlines()
    assert any(line.lower().startswith("compose run") for line in calls)
    assert not any(line.lower().startswith("compose build") for line in calls)
