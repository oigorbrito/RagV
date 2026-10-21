import hashlib
import os
from pathlib import Path
import subprocess  # nosec B404 - test harness invokes fixed Windows PowerShell with shell=False
import time

import pytest


ROOT = Path(__file__).resolve().parents[1]
POWERSHELL_EXE = str(Path(os.environ.get("WINDIR", r"C:\Windows")) / r"System32\WindowsPowerShell\v1.0\powershell.exe")
POWERSHELL_SEARCH_PATH = str(Path(POWERSHELL_EXE).parent)


def _check(condition: bool, message: str) -> None:
    if not condition:
        pytest.fail(message)


def _mock_docker_tools(directory: Path) -> tuple[Path, Path]:
    shim_dir = directory / "mock tools"
    shim_dir.mkdir(parents=True, exist_ok=True)
    mock_script = directory / "mock-docker.ps1"
    mock_script.write_text(
        "$DockerArgs = $args\n"
        "$operation = $DockerArgs -join ' '\n"
        "Add-Content -LiteralPath $env:RAGV_DOCKER_LOG -Value $operation\n"
        "if ($DockerArgs[0] -eq 'info') {\n"
        "  if ($env:RAGV_MOCK_MODE -eq 'info-fail') { [Console]::Error.WriteLine('synthetic info failure'); exit 31 }\n"
        "  if ($env:RAGV_MOCK_MODE -eq 'info-timeout') { exit 124 }\n"
        "  exit 0\n"
        "}\n"
        "if ($DockerArgs.Count -ge 2 -and $DockerArgs[0] -eq 'compose' -and $DockerArgs[1] -eq 'run') {\n"
        "  $p = $env:RAGV_MOCK_BACKUP_FILE; $payload = 'synthetic-readable-archive'\n"
        "  switch ($env:RAGV_MOCK_MODE) {\n"
        "    'missing' { exit 0 }\n"
        "    'backup-fail' { [IO.File]::WriteAllText($p, 'partial'); [IO.File]::WriteAllText($p+'.sha256', 'incomplete'); [Console]::Error.WriteLine('synthetic backup write failure'); exit 32 }\n"
        "    'empty' { $payload = '' }\n"
        "    'truncated' { [IO.File]::WriteAllText($p, 'truncated'); $temp = $p+'.expected'; [IO.File]::WriteAllText($temp, $payload); $h=(Get-FileHash -LiteralPath $temp -Algorithm SHA256).Hash.ToLowerInvariant(); Remove-Item -LiteralPath $temp; [IO.File]::WriteAllText($p+'.sha256', $h+'  '+[IO.Path]::GetFileName($p)); exit 0 }\n"
        "  }\n"
        "  [IO.File]::WriteAllText($p, $payload)\n"
        "  if ($env:RAGV_MOCK_MODE -ne 'missing-checksum') {\n"
        "    $h=(Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLowerInvariant()\n"
        "    if ($env:RAGV_MOCK_MODE -eq 'bad-checksum') { $h='0'*64 }\n"
        "    if ($env:RAGV_MOCK_MODE -eq 'wrong-name') { [IO.File]::WriteAllText($p+'.sha256', $h+'  other.dump'); exit 0 }\n"
        "    if ($env:RAGV_MOCK_MODE -eq 'malformed-checksum') { [IO.File]::WriteAllText($p+'.sha256', $h+'  '+[IO.Path]::GetFileName($p)+[Environment]::NewLine+'junk'); exit 0 }\n"
        "    [IO.File]::WriteAllText($p+'.sha256', $h+'  '+[IO.Path]::GetFileName($p))\n"
        "  }\n"
        "  if ($env:RAGV_MOCK_MODE -eq 'stderr-success') { [Console]::Error.WriteLine('synthetic diagnostic') }\n"
        "  exit 0\n"
        "}\n"
        "if ($DockerArgs.Count -ge 2 -and $DockerArgs[0] -eq 'compose' -and $DockerArgs[1] -eq 'build' -and $env:RAGV_MOCK_MODE -eq 'build-fail') { [Console]::Error.WriteLine('synthetic build failure'); exit 42 }\n"
        "if ($DockerArgs.Count -ge 2 -and $DockerArgs[0] -eq 'compose' -and $DockerArgs[1] -eq 'up' -and $env:RAGV_MOCK_MODE -eq 'up-fail') { [Console]::Error.WriteLine('synthetic apply failure'); exit 43 }\n"
        "exit 0\n",
        encoding="utf-8",
    )
    (shim_dir / "docker.cmd").write_text(
        '@echo off\r\n'
        'if /I "%1"=="info" if defined RAGV_INFO_MARKER echo entered>"%RAGV_INFO_MARKER%"\r\n'
        'if /I "%1"=="info" if %RAGV_DOCKER_DELAY% GTR 0 "%WINDIR%\\System32\\PING.EXE" -n %RAGV_DOCKER_DELAY% 127.0.0.1 >nul\r\n'
        '"%WINDIR%\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -File "%RAGV_MOCK_DOCKER_SCRIPT%" %*\r\n'
        'exit /b %ERRORLEVEL%\r\n',
        encoding="ascii",
    )
    return shim_dir, mock_script


def _environment(
    shim_dir: Path,
    mock_script: Path,
    log: Path,
    backup: Path,
    mode: str = "success",
    delay: int = 0,
    info_marker: Path | None = None,
) -> dict[str, str]:
    env = os.environ.copy()
    env["PATH"] = os.pathsep.join((str(shim_dir), POWERSHELL_SEARCH_PATH, env.get("PATH", "")))
    env["RAGV_DOCKER_LOG"] = str(log)
    env["RAGV_MOCK_DOCKER_SCRIPT"] = str(mock_script)
    env["RAGV_MOCK_BACKUP_FILE"] = str(backup)
    env["RAGV_MOCK_MODE"] = mode
    env["RAGV_DOCKER_DELAY"] = str(delay)
    if info_marker:
        env["RAGV_INFO_MARKER"] = str(info_marker)
    return env


def _run_update(script: Path, backup: Path, env: dict[str, str], timeout: int = 25) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # nosec B603,B607 - controlled PowerShell fixture; shell disabled
        [POWERSHELL_EXE, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script), "-BackupPath", str(backup)],
        env=env,
        text=True,
        capture_output=True,
        timeout=timeout,
        shell=False,
    )


def _start_update(script: Path, backup: Path, env: dict[str, str]) -> subprocess.Popen[str]:
    return subprocess.Popen(  # nosec B603,B607 - controlled PowerShell fixture; shell disabled
        [POWERSHELL_EXE, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script), "-BackupPath", str(backup)],
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
    )


def _wait_for_marker(process: subprocess.Popen[str], marker: Path) -> None:
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if marker.exists():
            return
        if process.poll() is not None:
            stdout, stderr = process.communicate()
            pytest.fail(f"Mocked updater exited before entering the critical section: {stdout} {stderr}")
        time.sleep(0.05)
    pytest.fail("Mocked updater did not reach the controlled Docker delay")


def _mock_calls(log: Path) -> list[str]:
    return log.read_text(encoding="utf-8", errors="replace").splitlines() if log.exists() else []


def test_update_verifier_fails_closed_on_signature_and_hash() -> None:
    text = (ROOT / "scripts/verify_windows_update.ps1").read_text(encoding="utf-8-sig")
    _check("Get-AuthenticodeSignature" in text, "Verifier must check Authenticode")
    _check("Status -ne 'Valid'" in text, "Verifier must reject invalid signatures")
    _check("Get-FileHash" in text, "Verifier must check the package hash")
    _check("hash do instalador não corresponde" in text, "Verifier must reject mismatching hashes")
    _check("version" in text and "publisher" in text, "Verifier must bind version and publisher")
    _check("Atualização rejeitada" in text, "Verifier must fail closed")


def test_update_verifier_does_not_apply_or_touch_docker() -> None:
    text = (ROOT / "scripts/verify_windows_update.ps1").read_text(encoding="utf-8-sig")
    _check("Start-Process" not in text, "Verifier must not apply an installer")
    _check("docker" not in text.lower(), "Installer verifier must not mutate Compose")
    _check("Copy-Item" not in text, "Verifier must not copy packages")
    _check("Remove-Item" not in text, "Verifier must not delete files")


def test_inno_installer_is_the_current_artifact_boundary() -> None:
    text = (ROOT / "packaging/windows/RagVDesktop.iss").read_text(encoding="utf-8-sig")
    _check("OutputBaseFilename" in text, "Inno installer output must remain explicit")
    _check("RagVDesktop.exe" in text, "Installer must package the desktop executable")
    _check("ProjectDir" in text, "Installer source root must remain explicit")
    _check("PrivilegesRequired=lowest" in text, "Installer must remain per-user")


def test_updater_uses_global_atomic_mutex_and_validates_archive_before_build() -> None:
    text = (ROOT / "scripts/update-ragv-desktop.ps1").read_text(encoding="utf-8-sig")
    _check('"Global\\RagV-ComposeUpdate-$repoHash"' in text, "Lock must cover all Windows sessions")
    _check("WaitOne(0)" in text, "Mutex acquisition must be nonblocking")
    _check("AbandonedMutexException" in text, "Abandoned lock must require recovery inspection")
    _check("ReleaseMutex()" in text, "Owned mutex must be released")
    _check(text.index("WaitOne(0)") < text.index("docker info"), "No Docker call may precede lock acquisition")
    _check(text.index("$backupFile.Length -le 0") < text.index("docker compose build"), "Empty archive must stop before build")
    _check(text.index("Get-FileHash -LiteralPath $backupFullPath") < text.index("docker compose build"), "Hash verification must precede build")


@pytest.mark.skipif(os.name != "nt", reason="Requires Windows mutexes, PowerShell, and cmd shim")
def test_concurrent_processes_are_exclusive_nonowner_cannot_unlock_and_success_releases_lock(tmp_path: Path) -> None:
    shim_dir, mock_script = _mock_docker_tools(tmp_path)
    script = ROOT / "scripts/update-ragv-desktop.ps1"
    first_backup = tmp_path / "first.dump"
    first_log = tmp_path / "first.log"
    marker = tmp_path / "first-entered-info"
    first_env = _environment(shim_dir, mock_script, first_log, first_backup, delay=4, info_marker=marker)
    first = _start_update(script, first_backup, first_env)
    _wait_for_marker(first, marker)

    for label in ("second", "third"):
        backup = tmp_path / f"{label}.dump"
        log = tmp_path / f"{label}.log"
        env = _environment(shim_dir, mock_script, log, backup)
        result = _run_update(script, backup, env)
        _check(result.returncode != 0, f"{label} updater must be rejected while first owns mutex")
        _check("em andamento" in (result.stdout + result.stderr), f"{label} rejection must be explicit")
        _check(not log.exists(), f"{label} rejected process must not call Docker")

    first_stdout, first_stderr = first.communicate(timeout=30)
    _check(first.returncode == 0, f"Owner should complete mocked success: {first_stdout} {first_stderr}")
    _check(sum(line.strip().lower() == "info" for line in _mock_calls(first_log)) == 1, "Only owner may enter Docker")

    retry_backup = tmp_path / "retry-after-success.dump"
    retry_log = tmp_path / "retry-after-success.log"
    retry = _run_update(script, retry_backup, _environment(shim_dir, mock_script, retry_log, retry_backup))
    _check(retry.returncode == 0, f"Mutex must be released after success: {retry.stdout} {retry.stderr}")
    _check(any(line.lower().startswith("compose up") for line in _mock_calls(retry_log)), "Retry after success must complete apply")


@pytest.mark.skipif(os.name != "nt", reason="Requires Windows named mutexes, PowerShell, and cmd shim")
def test_checkouts_with_distinct_identity_do_not_block_each_other(tmp_path: Path) -> None:
    shim_dir, mock_script = _mock_docker_tools(tmp_path)
    original_script = ROOT / "scripts/update-ragv-desktop.ps1"
    marker = tmp_path / "original-entered-info"
    original_backup = tmp_path / "original.dump"
    original_log = tmp_path / "original.log"
    original = _start_update(
        original_script,
        original_backup,
        _environment(shim_dir, mock_script, original_log, original_backup, delay=4, info_marker=marker),
    )
    _wait_for_marker(original, marker)

    other_root = tmp_path / "independent checkout"
    other_scripts = other_root / "scripts"
    other_scripts.mkdir(parents=True)
    other_script = other_scripts / "update-ragv-desktop.ps1"
    other_script.write_text(original_script.read_text(encoding="utf-8-sig"), encoding="utf-8")
    other_backup = tmp_path / "independent.dump"
    other_log = tmp_path / "independent.log"
    other = _run_update(other_script, other_backup, _environment(shim_dir, mock_script, other_log, other_backup))
    original_stdout, original_stderr = original.communicate(timeout=30)

    _check(other.returncode == 0, f"Independent checkout must not be blocked: {other.stdout} {other.stderr}")
    _check(original.returncode == 0, f"First checkout should complete: {original_stdout} {original_stderr}")
    _check(any(line.lower().startswith("compose build") for line in _mock_calls(other_log)), "Independent updater should reach build")


@pytest.mark.skipif(os.name != "nt", reason="Requires Windows PowerShell and mocked Docker")
def test_valid_backup_is_verified_before_build_and_no_secret_is_logged(tmp_path: Path) -> None:
    shim_dir, mock_script = _mock_docker_tools(tmp_path)
    backup = tmp_path / "valid [backup].dump"
    log = tmp_path / "calls.log"
    env = _environment(shim_dir, mock_script, log, backup, mode="stderr-success")
    env["RAGV_LOG_SENTINEL"] = "synthetic-log-marker-243"
    result = _run_update(ROOT / "scripts/update-ragv-desktop.ps1", backup, env)

    _check(result.returncode == 0, f"Valid archive/checksum should proceed: {result.stdout} {result.stderr}")
    _check(backup.exists() and Path(str(backup) + ".sha256").exists(), "Successful backup pair must remain available")
    expected = ["info", "compose run", "compose build", "compose up"]
    calls = _mock_calls(log)
    positions = [next((i for i, line in enumerate(calls) if line.lower().startswith(prefix)), -1) for prefix in expected]
    _check(all(position >= 0 for position in positions), f"Expected operations absent: {calls}")
    _check(positions == sorted(positions), f"Backup verification/apply order incorrect: {calls}")
    _check("synthetic-log-marker-243" not in "\n".join(calls), "Synthetic log sentinel must not appear in command logs")
    _check("synthetic diagnostic" not in result.stderr, "Raw Docker stderr must not be emitted to logs")
    _check(not any(line.lower().startswith("compose down") for line in calls), "Updater must not remove Compose volumes")


@pytest.mark.skipif(os.name != "nt", reason="Uses PowerShell without a Docker executable")
def test_missing_docker_executable_fails_closed(tmp_path: Path) -> None:
    shim_dir, mock_script = _mock_docker_tools(tmp_path)
    backup = tmp_path / "no-docker.dump"
    log = tmp_path / "no-docker.log"
    env = _environment(shim_dir, mock_script, log, backup)
    env["PATH"] = POWERSHELL_SEARCH_PATH
    result = _run_update(ROOT / "scripts/update-ragv-desktop.ps1", backup, env)
    _check(result.returncode != 0, "A missing Docker executable must fail closed")
    _check("Docker Desktop" in (result.stdout + result.stderr), "Missing Docker must return an explicit preflight error")
    _check(not log.exists(), "Missing Docker must not fall through to a stale exit code")


@pytest.mark.skipif(os.name != "nt", reason="Uses PowerShell and a Docker shim")
def test_backup_parent_must_be_a_directory_and_fail_before_docker(tmp_path: Path) -> None:
    shim_dir, mock_script = _mock_docker_tools(tmp_path)
    invalid_parent = tmp_path / "not-a-directory"
    invalid_parent.write_text("fixture", encoding="utf-8")
    backup = invalid_parent / "backup.dump"
    log = tmp_path / "calls.log"
    result = _run_update(
        ROOT / "scripts/update-ragv-desktop.ps1",
        backup,
        _environment(shim_dir, mock_script, log, backup),
    )
    _check(result.returncode != 0, "A file cannot be accepted as the backup directory")
    _check("backup aprovado" in (result.stdout + result.stderr), "Path preflight must explain invalid directory")
    _check(not log.exists(), "Invalid backup directory must fail before Docker")


@pytest.mark.skipif(os.name != "nt", reason="Uses PowerShell and a Docker shim")
@pytest.mark.parametrize(
    ("mode", "error_fragment"),
    [
        ("info-fail", "Docker Desktop"),
        ("info-timeout", "Docker Desktop"),
        ("backup-fail", "Backup ou valida"),
        ("missing", "ausente"),
        ("empty", "Backup vazio"),
        ("truncated", "Checksum do backup"),
        ("missing-checksum", "ausente"),
        ("bad-checksum", "Checksum do backup"),
        ("wrong-name", "Checksum do backup"),
        ("malformed-checksum", "malformado"),
    ],
)
def test_invalid_backup_and_docker_failures_stop_before_build(
    tmp_path: Path, mode: str, error_fragment: str
) -> None:
    shim_dir, mock_script = _mock_docker_tools(tmp_path)
    backup = tmp_path / f"{mode}.dump"
    log = tmp_path / "calls.log"
    result = _run_update(
        ROOT / "scripts/update-ragv-desktop.ps1",
        backup,
        _environment(shim_dir, mock_script, log, backup, mode=mode, delay=2 if mode == "info-timeout" else 0),
    )

    _check(result.returncode != 0, f"Fault mode {mode} must fail closed")
    _check(error_fragment.lower() in (result.stdout + result.stderr).lower(), f"Expected failure reason for {mode}: {result.stderr}")
    calls = _mock_calls(log)
    _check(not any(line.lower().startswith("compose build") for line in calls), f"Build must not run for {mode}: {calls}")
    _check(not any(line.lower().startswith("compose up") for line in calls), f"Apply must not run for {mode}: {calls}")
    if mode == "backup-fail":
        _check(not backup.exists() and not Path(str(backup) + ".sha256").exists(), "Partial backup artifacts from failed command should be cleaned")


@pytest.mark.skipif(os.name != "nt", reason="Uses PowerShell and a Docker shim")
@pytest.mark.parametrize("failure_function", ["Get-Content", "Get-FileHash"])
def test_backup_read_or_hash_errors_fail_closed(tmp_path: Path, failure_function: str) -> None:
    shim_dir, mock_script = _mock_docker_tools(tmp_path)
    source = (ROOT / "scripts/update-ragv-desktop.ps1").read_text(encoding="utf-8-sig")
    injected_script = tmp_path / "scripts" / "update-ragv-desktop.ps1"
    injected_script.parent.mkdir()
    parameter_end = source.index(")\n\n$ErrorActionPreference") + 2
    instrumented = source[:parameter_end] + f"\nfunction {failure_function} {{ throw 'synthetic {failure_function} failure' }}\n" + source[parameter_end:]
    injected_script.write_text(instrumented, encoding="utf-8")
    backup = tmp_path / "valid-but-unreadable.dump"
    log = tmp_path / "calls.log"
    result = _run_update(injected_script, backup, _environment(shim_dir, mock_script, log, backup))

    _check(result.returncode != 0, f"Injected {failure_function} failure must abort")
    _check(f"synthetic {failure_function} failure" in (result.stdout + result.stderr), "Expected I/O failure should be observable")
    _check(not any(line.lower().startswith("compose build") for line in _mock_calls(log)), "I/O failure must stop before build")


@pytest.mark.skipif(os.name != "nt", reason="Uses PowerShell and a Docker shim")
def test_failure_after_backup_releases_lock_keeps_recovery_pair_and_allows_retry(tmp_path: Path) -> None:
    shim_dir, mock_script = _mock_docker_tools(tmp_path)
    script = ROOT / "scripts/update-ragv-desktop.ps1"
    sentinel = tmp_path / "persistent-data-sentinel.bin"
    sentinel.write_bytes(b"persistent fixture remains unchanged")
    failed_backup = tmp_path / "build-failed.dump"
    failed_log = tmp_path / "build-failed.log"
    failed = _run_update(
        script,
        failed_backup,
        _environment(shim_dir, mock_script, failed_log, failed_backup, mode="build-fail"),
    )
    failed_calls = _mock_calls(failed_log)

    _check(failed.returncode != 0, "Build failure must be reported")
    _check("Falha ao construir" in (failed.stdout + failed.stderr), "Build failure must be explicit")
    _check(failed_backup.exists() and Path(str(failed_backup) + ".sha256").exists(), "Validated backup pair must survive pre-apply failure")
    _check(any(line.lower().startswith("compose build") for line in failed_calls), "Build failure injection must be reached")
    _check(not any(line.lower().startswith("compose up") for line in failed_calls), "Failed build must not apply services")
    _check(sentinel.read_bytes() == b"persistent fixture remains unchanged", "Persistent fixture must remain unchanged")
    _check(not any(line.lower().startswith("compose down") for line in failed_calls), "Failure path must not remove volumes")

    retry_backup = tmp_path / "retry-after-build-failure.dump"
    retry_log = tmp_path / "retry.log"
    retry = _run_update(script, retry_backup, _environment(shim_dir, mock_script, retry_log, retry_backup))
    _check(retry.returncode == 0, f"A later attempt must acquire the released mutex: {retry.stderr}")
    _check(any(line.lower().startswith("compose up") for line in _mock_calls(retry_log)), "Retry should reach mocked apply")


@pytest.mark.skipif(os.name != "nt", reason="Uses PowerShell and a Docker shim")
def test_apply_failure_is_detected_backup_retained_and_no_rollback_claimed(tmp_path: Path) -> None:
    shim_dir, mock_script = _mock_docker_tools(tmp_path)
    backup = tmp_path / "apply-failed.dump"
    log = tmp_path / "calls.log"
    result = _run_update(
        ROOT / "scripts/update-ragv-desktop.ps1",
        backup,
        _environment(shim_dir, mock_script, log, backup, mode="up-fail"),
    )
    calls = _mock_calls(log)

    _check(result.returncode != 0, "Apply failure must be surfaced")
    _check("Falha ao iniciar" in (result.stdout + result.stderr), "Apply failure should be explicit")
    _check(backup.exists() and Path(str(backup) + ".sha256").exists(), "Recovery pair must remain after apply failure")
    _check(any(line.lower().startswith("compose up") for line in calls), "Failure must occur at apply stage")
    _check(not any(line.lower().startswith("compose down") for line in calls), "No volume removal/automatic rollback command is allowed")


@pytest.mark.skipif(os.name != "nt", reason="Requires Windows named mutexes and PowerShell")
def test_abandoned_owner_requires_inspection_and_then_releases_lock(tmp_path: Path) -> None:
    shim_dir, mock_script = _mock_docker_tools(tmp_path)
    script = ROOT / "scripts/update-ragv-desktop.ps1"
    repo_identity = str(ROOT.resolve()).rstrip("\\").upper()
    mutex_hash = hashlib.sha256(repo_identity.encode("utf-8")).hexdigest().upper()
    lock_name = f"Global\\RagV-ComposeUpdate-{mutex_hash}"
    marker = tmp_path / "abandoned-owner-ready"
    holder_script = tmp_path / "abandon-owner.ps1"
    holder_script.write_text(
        "Add-Type -TypeDefinition @'\n"
        "using System; using System.Threading;\n"
        "public static class RagVAbandonProbe {\n"
        " public static Thread Start(string name, ManualResetEvent ready) {\n"
        "  var mutex = new Mutex(false, name);\n"
        "  var thread = new Thread(() => { mutex.WaitOne(); ready.Set(); Thread.Sleep(Timeout.Infinite); });\n"
        "  thread.Start(); return thread;\n"
        " }\n"
        "}\n"
        "'@\n"
        "$ready = New-Object System.Threading.ManualResetEvent($false)\n"
        "$owner = [RagVAbandonProbe]::Start($env:RAGV_LOCK_NAME, $ready)\n"
        "$ready.WaitOne()\n"
        "$owner.Abort()\n"
        "$owner.Join()\n"
        "[IO.File]::WriteAllText($env:RAGV_INFO_MARKER, 'abandoned')\n"
        "Start-Sleep -Seconds 10\n",
        encoding="utf-8",
    )
    holder_env = os.environ.copy()
    holder_env["PATH"] = os.pathsep.join((POWERSHELL_SEARCH_PATH, holder_env.get("PATH", "")))
    holder_env["RAGV_LOCK_NAME"] = lock_name
    holder_env["RAGV_INFO_MARKER"] = str(marker)
    holder = subprocess.Popen(  # nosec B603,B607 - test-owned mutex holder; shell disabled
        [POWERSHELL_EXE, "-NoProfile", "-File", str(holder_script)],
        env=holder_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        shell=False,
    )
    try:
        _wait_for_marker(holder, marker)
        retry_backup = tmp_path / "after-interruption.dump"
        retry_log = tmp_path / "after-interruption.log"
        retry = _run_update(
            script,
            retry_backup,
            _environment(shim_dir, mock_script, retry_log, retry_backup),
        )
        _check(retry.returncode != 0, "First retry after abandoned mutex must stop for inspection")
        _check("foi interrompida" in (retry.stdout + retry.stderr), "Abandoned mutex should require recovery inspection")
        _check(not retry_log.exists(), "Abandoned lock detection must precede Docker")

        later_backup = tmp_path / "after-inspection.dump"
        later_log = tmp_path / "after-inspection.log"
        later = _run_update(script, later_backup, _environment(shim_dir, mock_script, later_log, later_backup))
        _check(later.returncode == 0, f"Lock should release after controlled abandoned-lock error: {later.stderr}")
    finally:
        if holder.poll() is None:
            holder.terminate()
            holder.communicate(timeout=10)


@pytest.mark.skipif(os.name != "nt", reason="Requires Windows global objects and PowerShell")
def test_mutex_creation_failure_blocks_all_docker_calls(tmp_path: Path) -> None:
    shim_dir, mock_script = _mock_docker_tools(tmp_path)
    repo_identity = str(ROOT.resolve()).rstrip("\\").upper()
    mutex_hash = hashlib.sha256(repo_identity.encode("utf-8")).hexdigest().upper()
    lock_name = f"Global\\RagV-ComposeUpdate-{mutex_hash}"
    marker = tmp_path / "event-holder-ready"
    holder_script = tmp_path / "hold-name.ps1"
    holder_script.write_text(
        "$event = [System.Threading.EventWaitHandle]::new($false, [System.Threading.EventResetMode]::ManualReset, $env:RAGV_LOCK_NAME)\n"
        "[IO.File]::WriteAllText($env:RAGV_INFO_MARKER, 'ready')\n"
        "Start-Sleep -Seconds 30\n"
        "$event.Dispose()\n",
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["PATH"] = os.pathsep.join((str(shim_dir), POWERSHELL_SEARCH_PATH, env.get("PATH", "")))
    env["RAGV_LOCK_NAME"] = lock_name
    env["RAGV_INFO_MARKER"] = str(marker)
    holder = subprocess.Popen(  # nosec B603,B607 - test-owned event holder; shell disabled
        [POWERSHELL_EXE, "-NoProfile", "-File", str(holder_script)],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        shell=False,
    )
    try:
        _wait_for_marker(holder, marker)
        backup = tmp_path / "must-not-run.dump"
        log = tmp_path / "must-not-run.log"
        result = _run_update(
            ROOT / "scripts/update-ragv-desktop.ps1",
            backup,
            _environment(shim_dir, mock_script, log, backup),
        )
        _check(result.returncode != 0, "Mutex object type collision must fail closed")
        _check(not log.exists(), "Mutex creation/acquisition failure must occur before Docker")
    finally:
        if holder.poll() is None:
            holder.terminate()
            holder.communicate(timeout=10)
