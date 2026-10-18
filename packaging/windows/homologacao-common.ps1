# Rotinas locais exclusivas do instalador de homologação. Windows PowerShell 5.1 / PowerShell 7.
$ErrorActionPreference = 'Stop'
$script:HmlRoot = Join-Path $env:LOCALAPPDATA 'RagV-Homologacao'
$script:HmlRuntime = Join-Path $PSScriptRoot 'runtime'
$script:HmlEnv = Join-Path $script:HmlRoot '.env'
$script:HmlStage = 'pré-requisitos'

function Set-HmlPrivatePath([string]$Path) {
    $item = Get-Item -LiteralPath $Path
    $sid = [Security.Principal.WindowsIdentity]::GetCurrent().User
    $system = New-Object Security.Principal.SecurityIdentifier('S-1-5-18')
    if ($item.PSIsContainer) {
        $acl = New-Object Security.AccessControl.DirectorySecurity
        $inherit = [Security.AccessControl.InheritanceFlags]'ContainerInherit,ObjectInherit'
    } else {
        $acl = New-Object Security.AccessControl.FileSecurity
        $inherit = [Security.AccessControl.InheritanceFlags]::None
    }
    $acl.SetOwner($sid)
    $acl.SetAccessRuleProtection($true, $false)
    foreach ($identity in @($sid, $system)) {
        $rule = New-Object Security.AccessControl.FileSystemAccessRule($identity, 'FullControl', $inherit, 'None', 'Allow')
        $acl.AddAccessRule($rule)
    }
    if ($PSVersionTable.PSVersion.Major -ge 7) {
        [IO.FileSystemAclExtensions]::SetAccessControl($item, $acl)
        $actual = [IO.FileSystemAclExtensions]::GetAccessControl($item)
    } else {
        $item.SetAccessControl($acl)
        $actual = $item.GetAccessControl()
    }
    if (-not $actual.AreAccessRulesProtected) { throw 'A proteção de permissões do perfil não foi aplicada.' }
    $rules = @($actual.GetAccessRules($true, $true, [Security.Principal.SecurityIdentifier]))
    if ($rules.Count -ne 2) { throw 'O perfil contém permissões inesperadas.' }
    foreach ($rule in $rules) {
        if ($rule.IdentityReference.Value -notin @($sid.Value, $system.Value) -or $rule.AccessControlType -ne 'Allow' -or $rule.IsInherited -or $rule.FileSystemRights -ne 'FullControl') {
            throw 'A verificação de permissões do perfil falhou.'
        }
    }
}

function Initialize-HmlPaths {
    foreach ($path in @('compose.yaml','compose.homologacao.yaml','Dockerfile','HOMOLOGACAO.txt','scripts/bootstrap_homologation.py','sql/034_acquisition_authorizations.sql')) {
        if (-not (Test-Path -LiteralPath (Join-Path $script:HmlRuntime $path))) { throw "Pacote instalado incompleto: runtime/$path. Reinstale a homologação." }
    }
    New-Item -ItemType Directory -Path $script:HmlRoot -Force | Out-Null
    Set-HmlPrivatePath $script:HmlRoot
    # Compatibilidade somente com o perfil gerado pelo instalador anterior, nunca com o .env habitual.
    $legacy = Join-Path $script:HmlRoot 'project/.env'
    if (-not (Test-Path $script:HmlEnv) -and (Test-Path $legacy)) {
        $old = Get-Content -LiteralPath $legacy -Encoding UTF8
        if (-not ($old -match '^COMPOSE_PROJECT_NAME=ragv-hml-[a-f0-9]{12}$')) { throw 'O perfil anterior não é um perfil de homologação válido.' }
        Copy-Item -LiteralPath $legacy -Destination $script:HmlEnv
    }
    foreach ($file in @($script:HmlEnv, (Join-Path $script:HmlRoot 'access-token.txt'))) {
        if (Test-Path $file) { Set-HmlPrivatePath $file }
    }
    # Limpa variáveis herdadas; o único arquivo de configuração aceito é o deste perfil.
    $source = (Get-Content (Join-Path $script:HmlRuntime 'compose.yaml') -Raw -Encoding UTF8) + (Get-Content (Join-Path $script:HmlRuntime 'compose.homologacao.yaml') -Raw -Encoding UTF8)
    $names = @('COMPOSE_FILE','COMPOSE_PROJECT_NAME','COMPOSE_PROFILES','COMPOSE_ENV_FILES','COMPOSE_DISABLE_ENV_FILE') + @([regex]::Matches($source, '\$\{([A-Z][A-Z0-9_]*)') | ForEach-Object { $_.Groups[1].Value })
    foreach ($name in ($names | Select-Object -Unique)) { Remove-Item "Env:$name" -ErrorAction SilentlyContinue }
}

function Get-HmlSettings {
    $settings = @{}
    foreach ($line in (Get-Content -LiteralPath $script:HmlEnv -Encoding UTF8)) {
        if ($line -match '^([A-Z][A-Z0-9_]*)=(.*)$') { $settings[$matches[1]] = $matches[2] }
    }
    if ($settings.COMPOSE_PROJECT_NAME -notmatch '^ragv-hml-[a-f0-9]{12}$') { throw 'Identificador de homologação inválido.' }
    $port = 0
    if (-not [int]::TryParse($settings.RPY_API_PORT, [ref]$port) -or $port -lt 1024 -or $port -gt 65535) { throw 'Porta local da homologação inválida.' }
    return $settings
}

function Write-HmlEvent([string]$Stage, [int]$Code) {
    # Sem stdout/stderr de containers, tokens, URL de banco ou dados processuais.
    $event = @{at=[DateTime]::UtcNow.ToString('o');stage=$Stage;exit_code=$Code;ps_version=$PSVersionTable.PSVersion.ToString();ps_edition=$PSVersionTable.PSEdition}
    Add-Content -LiteralPath (Join-Path $script:HmlRoot 'startup.jsonl') -Value ($event | ConvertTo-Json -Compress) -Encoding UTF8
}

function Invoke-HmlDocker([string]$Stage, [string[]]$DockerArgs) {
    $script:HmlStage = $Stage
    if ($script:HmlStatusLabel) { $script:HmlStatusLabel.Text = $Stage; [Windows.Forms.Application]::DoEvents() }
    $start = New-Object Diagnostics.ProcessStartInfo
    $start.FileName = (Get-Command docker.exe -ErrorAction Stop).Source
    # Todos os argumentos são internos/caminhos locais; aspas não são aceitas em caminhos Windows.
    $start.Arguments = (($DockerArgs | ForEach-Object { '"' + $_.Replace('"','\"') + '"' }) -join ' ')
    $start.UseShellExecute = $false
    $start.CreateNoWindow = $true
    $start.RedirectStandardOutput = $true
    $start.RedirectStandardError = $true
    $process = New-Object Diagnostics.Process
    $process.StartInfo = $start
    $process.Start() | Out-Null
    $stdout = $process.StandardOutput.ReadToEndAsync()
    $stderr = $process.StandardError.ReadToEndAsync()
    while (-not $process.WaitForExit(100)) { if ($script:HmlStatusLabel) { [Windows.Forms.Application]::DoEvents() } }
    $output = $stdout.GetAwaiter().GetResult()
    $null = $stderr.GetAwaiter().GetResult()
    $code = $process.ExitCode
    $process.Dispose()
    Write-HmlEvent $Stage $code
    if ($code -ne 0) { throw "A etapa '$Stage' falhou (código $code). Veja startup.jsonl no perfil de homologação." }
    return $output
}

function Get-HmlComposeArgs([hashtable]$Settings) {
    return @('compose','--project-name',$Settings.COMPOSE_PROJECT_NAME,'--project-directory',$script:HmlRuntime,'--env-file',$script:HmlEnv,'-f',(Join-Path $script:HmlRuntime 'compose.yaml'),'-f',(Join-Path $script:HmlRuntime 'compose.homologacao.yaml'))
}
