$ErrorActionPreference = 'Stop'
$profileRoot = Join-Path $env:LOCALAPPDATA 'RagV-Homologacao'
$project = Join-Path $profileRoot 'project'
$envFile = Join-Path $project '.env'
$revision = 'a414b2a1d478ccfbf33611a7c40437dd3f90f3b7'
$composeProject = $null

function New-Secret([int]$Bytes = 32) {
    $buffer = New-Object byte[] $Bytes
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($buffer) } finally { $rng.Dispose() }
    return [Convert]::ToBase64String($buffer).TrimEnd('=').Replace('+','-').Replace('/','_')
}
function Get-FreePort([int]$Preferred) {
    $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $Preferred)
    try { $listener.Start(); return $Preferred }
    catch {
        $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
        $listener.Start(); return ([System.Net.IPEndPoint]$listener.LocalEndpoint).Port
    }
    finally { $listener.Stop() }
}

try {
    if (-not (Test-Path (Join-Path $project 'compose.yaml'))) { throw "Pacote de homologação não encontrado em $project. Reinstale o instalador." }
    if (-not (Test-Path $envFile)) {
        $db = New-Secret
        $token = New-Secret
        $tenant = [guid]::NewGuid().ToString()
        $apiPort = Get-FreePort 18080
        $composeProject = 'ragv-hml-' + ([guid]::NewGuid().ToString('N').Substring(0, 12))
        @(
            "COMPOSE_PROJECT_NAME=$composeProject"
            "POSTGRES_PASSWORD=$db"
            "RPY_OPS_TOKEN=$(New-Secret)"
            "JUDIT_WEBHOOK_TOKEN=$(New-Secret)"
            "RPY_API_PORT=$apiPort"
            'RPY_TENANT_PROCESSES={}'
            "RPY_BEARER_TOKENS={`"$token`":`"$tenant`"}"
            'RPY_DEMO_BEARER_TOKEN='
            'DATAJUD_ENABLED=false'
            'DATAJUD_AUTHORIZED_USE=false'
            'DATAJUD_API_KEY='
            'JUDIT_API_KEY='
            'ANTHROPIC_API_KEY='
            'OPENAI_API_KEY='
        ) | Set-Content -LiteralPath $envFile -Encoding ascii
        $acl = Get-Acl $envFile
        $acl.SetAccessRuleProtection($true, $false)
        $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
        $rule = New-Object System.Security.AccessControl.FileSystemAccessRule($identity,'FullControl','Allow')
        $acl.SetAccessRule($rule)
        Set-Acl -LiteralPath $envFile -AclObject $acl
        $tokenFile = Join-Path $profileRoot 'access-token.txt'
        Set-Content -LiteralPath $tokenFile -Value $token -Encoding ascii
        Set-Acl -LiteralPath $tokenFile -AclObject $acl
        Set-Content -LiteralPath (Join-Path $profileRoot 'diagnostics.txt') -Value "RagV Homologação`nVersão 0.1.1-hml`nSHA da aplicação $revision`nCompose $composeProject`nAPI http://127.0.0.1:$apiPort`nTenant sintético $tenant" -Encoding utf8
    }
    $envLines = Get-Content -LiteralPath $envFile
    # Não herdar credenciais/configuração de outras instalações do shell do usuário.
    $composeNames = @('COMPOSE_FILE','COMPOSE_PROJECT_NAME','POSTGRES_PASSWORD','PGPORT','RPY_API_PORT','RPY_BEARER_TOKENS','RPY_TENANT_PROCESSES','RPY_OPS_TOKEN','JUDIT_WEBHOOK_TOKEN','JUDIT_WEBHOOK_TENANT_ID','JUDIT_API_KEY','JUDIT_CALLBACK_URL','JUDIT_ATTACHMENTS_ENABLED','JUDIT_ATTACHMENT_DOWNLOAD_MODE','DATAJUD_ENABLED','DATAJUD_AUTHORIZED_USE','DATAJUD_API_KEY','DATAJUD_BASE_URL','DATAJUD_TIMEOUT_SECONDS','ANTHROPIC_API_KEY','OPENAI_API_KEY')
    foreach ($name in $composeNames) { [Environment]::SetEnvironmentVariable($name, $null, 'Process') }
    if (-not $composeProject) { $composeProject = (($envLines | Where-Object { $_ -like 'COMPOSE_PROJECT_NAME=*' } | Select-Object -First 1) -replace '^COMPOSE_PROJECT_NAME=','') }
    if ($composeProject -notmatch '^ragv-hml-[a-f0-9]{12}$') { throw 'Identificador de perfil de homologação inválido.' }
    $apiPort = [int](($envLines | Where-Object { $_ -like 'RPY_API_PORT=*' } | Select-Object -First 1) -replace '^RPY_API_PORT=','')
    $env:RPY_DESKTOP_URL = "http://127.0.0.1:$apiPort"
    Push-Location $project
    try {
        docker info *> $null
        if ($LASTEXITCODE -ne 0) { throw 'Docker Desktop precisa estar iniciado e usando containers Linux.' }
        docker compose --project-name $composeProject -f compose.yaml -f compose.homologacao.yaml config --quiet
        if ($LASTEXITCODE -ne 0) { throw 'Configuração Docker inválida.' }
        $packageLine = Get-Content (Join-Path $project 'HOMOLOGACAO.txt') | Where-Object { $_ -like 'Package SHA: *' }
        $packageSha = $packageLine -replace '^Package SHA: ', ''
        if ($packageSha -notmatch '^[a-f0-9]{40}$') { throw 'Identidade do pacote ausente ou inválida.' }
        $imageTag = "ragv-homologacao:$($packageSha.Substring(0,12))"
        $imageIds = @(docker image ls --quiet --filter "reference=$imageTag")
        $imageExists = ($imageIds.Count -gt 0)
        if (-not $imageExists) {
            docker compose --project-name $composeProject -f compose.yaml -f compose.homologacao.yaml build api
            if ($LASTEXITCODE -ne 0) { throw 'Falha ao construir imagens de homologação.' }
        }
        docker compose --project-name $composeProject -f compose.yaml -f compose.homologacao.yaml up -d --no-build postgres migrate api worker-1 worker-2 scheduler
        if ($LASTEXITCODE -ne 0) { throw 'Falha ao iniciar serviços de homologação.' }
        $ready = $false
        for ($i=0; $i -lt 90; $i++) {
            try { $r=Invoke-WebRequest -Uri "$($env:RPY_DESKTOP_URL)/ready" -UseBasicParsing -TimeoutSec 3; if ($r.StatusCode -eq 200) { $ready=$true; break } } catch { Start-Sleep -Seconds 2 }
        }
        if (-not $ready) { throw 'API não ficou pronta; consulte docker compose logs no diretório de homologação.' }
        docker compose --project-name $composeProject -f compose.yaml -f compose.homologacao.yaml run --rm --no-deps api python scripts/bootstrap_homologation.py
        if ($LASTEXITCODE -ne 0) { throw 'Falha ao preparar tenant vazio de homologação.' }
        & (Join-Path $PSScriptRoot 'RagVDesktop.exe')
        if ($LASTEXITCODE -ne 0) { throw "RagVDesktop encerrou com código $LASTEXITCODE." }
    } finally { Pop-Location }
} catch {
    $_ | Out-String | Set-Content -LiteralPath (Join-Path $profileRoot 'last-error.txt') -Encoding utf8
    Add-Type -AssemblyName System.Windows.Forms
    [System.Windows.Forms.MessageBox]::Show($_.Exception.Message, 'RagV Homologação', 'OK', 'Error') | Out-Null
    exit 1
}
