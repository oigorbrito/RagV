param(
    [Parameter(Mandatory = $true)]
    [string]$BackupPath
)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$backupFullPath = [System.IO.Path]::GetFullPath($BackupPath)
$backupDirectory = Split-Path -Parent $backupFullPath
$backupName = Split-Path -Leaf $backupFullPath

if (-not (Test-Path $backupDirectory)) {
    throw "O diretório de backup aprovado não existe: $backupDirectory"
}
if (Test-Path $backupFullPath) {
    throw "O destino do backup já existe; escolha um caminho novo: $backupFullPath"
}

# Serializa execuções do updater no mesmo checkout/sessão do Windows. O nome
# deriva do caminho real do repositório para não bloquear outros projetos RagV.
$repoIdentity = [System.IO.Path]::GetFullPath($repo).TrimEnd('\').ToUpperInvariant()
$repoHashBytes = [System.Security.Cryptography.SHA256]::Create().ComputeHash([System.Text.Encoding]::UTF8.GetBytes($repoIdentity))
$repoHash = [System.BitConverter]::ToString($repoHashBytes).Replace('-', '').Substring(0, 24)
$mutexName = "Local\RagV-ComposeUpdate-$repoHash"
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
        docker info *> $null
        if ($LASTEXITCODE -ne 0) { throw "Docker Desktop não está em execução." }

        # Reutiliza o script de backup testado dentro da imagem PostgreSQL, sem
        # transferir dados do volume para uma imagem da aplicação.
        $repoMount = "${repo}:/work:ro"
        $backupMount = "${backupDirectory}:/backup"
        docker compose run --rm --no-deps -v $repoMount -v $backupMount --entrypoint sh postgres -c 'DATABASE_URL="postgresql://rpy:$POSTGRES_PASSWORD@postgres:5432/rpy" sh /work/scripts/backup_database.sh "/backup/$1"' sh $backupName
        if ($LASTEXITCODE -ne 0) {
            Remove-Item -LiteralPath $backupFullPath, "$backupFullPath.sha256" -Force -ErrorAction SilentlyContinue
            throw "Backup ou validação falhou; atualização cancelada."
        }
        $backupChecksumPath = "$backupFullPath.sha256"
        if (-not (Test-Path -LiteralPath $backupFullPath -PathType Leaf) -or
            -not (Test-Path -LiteralPath $backupChecksumPath -PathType Leaf)) {
            throw "Backup validado ou checksum ausente no destino; atualização cancelada."
        }
        $checksumFields = (Get-Content -LiteralPath $backupChecksumPath -Raw).Trim() -split '\s+'
        $actualBackupHash = (Get-FileHash -LiteralPath $backupFullPath -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($checksumFields.Count -lt 1 -or $checksumFields[0] -notmatch '^[a-fA-F0-9]{64}$' -or
            $checksumFields[0].ToLowerInvariant() -ne $actualBackupHash) {
            throw "Checksum do backup não confere; atualização cancelada."
        }

        # Um único conjunto versionado: migração, API (inclui frontend), workers e scheduler.
        docker compose build migrate api worker-1 worker-2 scheduler
        if ($LASTEXITCODE -ne 0) { throw "Falha ao construir o conjunto coordenado; serviços não foram atualizados." }

        docker compose up -d --no-build migrate api worker-1 worker-2 scheduler
        if ($LASTEXITCODE -ne 0) { throw "Falha ao iniciar o conjunto coordenado RagV." }
    }
    finally {
        Pop-Location
    }
}
finally {
    if ($mutexOwned) { $updateMutex.ReleaseMutex() }
    $updateMutex.Dispose()
}
