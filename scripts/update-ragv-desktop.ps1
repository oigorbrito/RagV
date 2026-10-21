param(
    [Parameter(Mandatory = $true)]
    [string]$BackupPath
)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$backupFullPath = [System.IO.Path]::GetFullPath($BackupPath)
$backupDirectory = Split-Path -Parent $backupFullPath
$backupName = Split-Path -Leaf $backupFullPath

if (-not (Test-Path -LiteralPath $backupDirectory -PathType Container)) {
    throw "O diretório de backup aprovado não existe ou não é diretório: $backupDirectory"
}
if (Test-Path -LiteralPath $backupFullPath) {
    throw "O destino do backup já existe; escolha um caminho novo: $backupFullPath"
}

# Serializa execuções do updater no mesmo checkout, inclusive entre sessões
# Windows. O nome por caminho não bloqueia checkouts independentes.
$repoIdentity = [System.IO.Path]::GetFullPath($repo).TrimEnd('\').ToUpperInvariant()
$identityHasher = [System.Security.Cryptography.SHA256]::Create()
try {
    $repoHashBytes = $identityHasher.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($repoIdentity))
}
finally {
    $identityHasher.Dispose()
}
$repoHash = [System.BitConverter]::ToString($repoHashBytes).Replace('-', '')
$mutexName = "Global\RagV-ComposeUpdate-$repoHash"
$updateMutex = [System.Threading.Mutex]::new($false, $mutexName)
$mutexOwned = $false

try {
    try {
        $mutexOwned = $updateMutex.WaitOne(0)
    }
    catch [System.Threading.AbandonedMutexException] {
        # O mutex fica adquirido pelo processo que recebe AbandonedMutexException.
        $mutexOwned = $true
        throw "Uma execução anterior do atualizador foi interrompida. Verifique os serviços e o backup antes de tentar novamente."
    }
    if (-not $mutexOwned) {
        throw "Outra atualização RagV já está em andamento neste checkout."
    }

    Push-Location $repo
    try {
        $dockerInfoExitCode = 1
        $previousErrorActionPreference = $ErrorActionPreference
        try {
            $ErrorActionPreference = 'Continue'
            $LASTEXITCODE = 1
            docker info 2>&1 | Out-Null
            $dockerInfoExitCode = $LASTEXITCODE
        }
        catch {
            $dockerInfoExitCode = 1
        }
        finally {
            $ErrorActionPreference = $previousErrorActionPreference
        }
        if ($dockerInfoExitCode -ne 0) { throw "Docker Desktop não está em execução." }

        # Reutiliza o script de backup testado dentro da imagem PostgreSQL, sem
        # transferir dados do volume para uma imagem da aplicação.
        $repoMount = "${repo}:/work:ro"
        $backupMount = "${backupDirectory}:/backup"
        $backupCommandFailed = $false
        $previousErrorActionPreference = $ErrorActionPreference
        try {
            $ErrorActionPreference = 'Continue'
            $LASTEXITCODE = 1
            docker compose run --rm --no-deps -v $repoMount -v $backupMount --entrypoint sh postgres -c 'DATABASE_URL="postgresql://rpy:$POSTGRES_PASSWORD@postgres:5432/rpy" sh /work/scripts/backup_database.sh "/backup/$1"' sh $backupName 2>&1 | Out-Null
            if ($LASTEXITCODE -ne 0) { $backupCommandFailed = $true }
        }
        catch {
            $backupCommandFailed = $true
        }
        finally {
            $ErrorActionPreference = $previousErrorActionPreference
        }
        if ($backupCommandFailed) {
            Remove-Item -LiteralPath $backupFullPath, "$backupFullPath.sha256" -Force -ErrorAction SilentlyContinue
            throw "Backup ou validação falhou; atualização cancelada."
        }
        $backupChecksumPath = "$backupFullPath.sha256"
        if (-not (Test-Path -LiteralPath $backupFullPath -PathType Leaf) -or
            -not (Test-Path -LiteralPath $backupChecksumPath -PathType Leaf)) {
            throw "Backup validado ou checksum ausente no destino; atualização cancelada."
        }
        $backupFile = Get-Item -LiteralPath $backupFullPath -ErrorAction Stop
        if ($backupFile.Length -le 0) {
            throw "Backup vazio; atualização cancelada."
        }
        $checksumLines = @(Get-Content -LiteralPath $backupChecksumPath -ErrorAction Stop)
        if ($checksumLines.Count -ne 1) {
            throw "Manifesto de checksum malformado; atualização cancelada."
        }
        $checksumFields = $checksumLines[0].Trim() -split '\s+', 2
        $actualBackupHash = (Get-FileHash -LiteralPath $backupFullPath -Algorithm SHA256 -ErrorAction Stop).Hash.ToLowerInvariant()
        if ($checksumFields.Count -ne 2 -or $checksumFields[0] -notmatch '^[a-fA-F0-9]{64}$' -or
            $checksumFields[1] -cne $backupName -or $checksumFields[0].ToLowerInvariant() -ne $actualBackupHash) {
            throw "Checksum do backup não confere; atualização cancelada."
        }

        # Um único conjunto versionado: migração, API (inclui frontend), workers e scheduler.
        $buildExitCode = 1
        $previousErrorActionPreference = $ErrorActionPreference
        try {
            $ErrorActionPreference = 'Continue'
            $LASTEXITCODE = 1
            docker compose build migrate api worker-1 worker-2 scheduler 2>&1 | Out-Null
            $buildExitCode = $LASTEXITCODE
        }
        catch {
            $buildExitCode = 1
        }
        finally {
            $ErrorActionPreference = $previousErrorActionPreference
        }
        if ($buildExitCode -ne 0) { throw "Falha ao construir o conjunto coordenado; serviços não foram atualizados." }

        $applyExitCode = 1
        $previousErrorActionPreference = $ErrorActionPreference
        try {
            $ErrorActionPreference = 'Continue'
            $LASTEXITCODE = 1
            docker compose up -d --no-build migrate api worker-1 worker-2 scheduler 2>&1 | Out-Null
            $applyExitCode = $LASTEXITCODE
        }
        catch {
            $applyExitCode = 1
        }
        finally {
            $ErrorActionPreference = $previousErrorActionPreference
        }
        if ($applyExitCode -ne 0) { throw "Falha ao iniciar o conjunto coordenado RagV." }
    }
    finally {
        Pop-Location
    }
}
finally {
    if ($mutexOwned) { $updateMutex.ReleaseMutex() }
    $updateMutex.Dispose()
}
