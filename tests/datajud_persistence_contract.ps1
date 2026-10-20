param([string]$Root, [string]$Scratch, [switch]$CheckCompose)
$ErrorActionPreference = 'Stop'
function Assert-Contract([bool]$Condition, [string]$Message) {
    if (-not $Condition) { throw $Message }
}
function Import-Function([string]$Path, [string]$Name) {
    $tokens = $null; $errors = $null
    $ast = [Management.Automation.Language.Parser]::ParseFile($Path, [ref]$tokens, [ref]$errors)
    Assert-Contract ($errors.Count -eq 0) 'PowerShell parse failed'
    $definition = $ast.Find({param($n) $n -is [Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq $Name}, $true)
    Assert-Contract ($null -ne $definition) 'Function not found'
    return $definition.Extent.Text
}
. (Join-Path $Root 'packaging/windows/homologacao-common.ps1')
$script:HmlRoot = Join-Path $Scratch 'profile with spaces'
$script:HmlEnv = Join-Path $script:HmlRoot '.env'
$script:HmlRuntime = Join-Path $Scratch 'package with spaces/runtime'
New-Item -ItemType Directory -Path $script:HmlRuntime -Force | Out-Null
foreach ($path in @('compose.yaml','compose.homologacao.yaml','Dockerfile','HOMOLOGACAO.txt','scripts/bootstrap_homologation.py','sql/034_acquisition_authorizations.sql')) {
    $target = Join-Path $script:HmlRuntime $path
    New-Item -ItemType Directory -Path (Split-Path $target -Parent) -Force | Out-Null
    $source = Join-Path $Root $path
    if (Test-Path $source) { Copy-Item $source $target } else { Set-Content $target 'synthetic package' }
}
# ACL behavior has separate Windows contracts. This test must never touch a real profile.
function Set-HmlPrivatePath([string]$Path) {
    Assert-Contract ([IO.Path]::GetFullPath($Path).StartsWith([IO.Path]::GetFullPath($Scratch))) 'Profile escaped scratch directory'
}
$launcher = Join-Path $Root 'packaging/windows/start-homologacao.ps1'
$tokens = $null; $errors = $null
$ast = [Management.Automation.Language.Parser]::ParseFile($launcher, [ref]$tokens, [ref]$errors)
$creation = $ast.Find({param($n) $n -is [Management.Automation.Language.IfStatementAst] -and $n.Extent.Text.StartsWith('if (-not (Test-Path $script:HmlEnv))')}, $true)
Assert-Contract ($null -ne $creation) 'Profile creation contract not found'
Initialize-HmlPaths
Invoke-Expression $creation.Extent.Text
$settings = Get-HmlSettings
Assert-Contract ($settings.DATAJUD_ENABLED -eq 'false' -and $settings.DATAJUD_AUTHORIZED_USE -eq 'false' -and -not $settings.DATAJUD_API_KEY) 'New profile must be disabled'
$project = $settings.COMPOSE_PROJECT_NAME
$initial = [IO.File]::ReadAllBytes($script:HmlEnv)
Invoke-Expression (Import-Function (Join-Path $Root 'packaging/windows/configurar-datajud.ps1') 'Save-DataJudConfiguration')
$denied = $false
try { Save-DataJudConfiguration -Key 'synthetic-datajud-secret-123456' -AuthorizedUse $false } catch { $denied = $true }
Assert-Contract $denied 'Unauthorized activation must fail'
Assert-Contract ([Convert]::ToBase64String($initial) -ceq [Convert]::ToBase64String([IO.File]::ReadAllBytes($script:HmlEnv))) 'Denied activation changed profile'
Save-DataJudConfiguration -Key 'synthetic-datajud-secret-123456' -AuthorizedUse $true
$persisted = [Convert]::ToBase64String([IO.File]::ReadAllBytes($script:HmlEnv))
$dev = Join-Path $Scratch 'development.env'
Set-Content $dev 'development sentinel - never copy credentials here'
$devBefore = [IO.File]::ReadAllText($dev)
# Reopening and replacing the application runtime must reuse the same profile.
for ($i = 0; $i -lt 3; $i++) {
    if ($i -eq 2) {
        $updated = Join-Path $Scratch 'updated with spaces/runtime'
        New-Item -ItemType Directory -Path (Split-Path $updated -Parent) -Force | Out-Null
        Copy-Item $script:HmlRuntime $updated -Recurse
        $script:HmlRuntime = $updated
    }
    $env:DATAJUD_ENABLED = 'false'
    $env:DATAJUD_API_KEY = 'ambient-value-must-not-be-used'
    $env:COMPOSE_PROJECT_NAME = 'development-wrong-project'
    Initialize-HmlPaths
    Invoke-Expression $creation.Extent.Text
    $settings = Get-HmlSettings
    Assert-Contract ($settings.DATAJUD_ENABLED -eq 'true' -and $settings.DATAJUD_AUTHORIZED_USE -eq 'true') 'Authorization lost on reopen/update'
    Assert-Contract ($settings.DATAJUD_API_KEY -ceq 'synthetic-datajud-secret-123456') 'Key lost on reopen/update'
    Assert-Contract ($settings.COMPOSE_PROJECT_NAME -ceq $project) 'Project changed on reopen/update'
    Assert-Contract (-not $env:DATAJUD_API_KEY -and -not $env:DATAJUD_ENABLED -and -not $env:COMPOSE_PROJECT_NAME) 'Ambient override not removed'
    Assert-Contract ($persisted -ceq [Convert]::ToBase64String([IO.File]::ReadAllBytes($script:HmlEnv))) 'Existing env was rewritten'
    Assert-Contract ($devBefore -ceq [IO.File]::ReadAllText($dev)) 'Development configuration changed'
}
# An explicitly authorized reapply also preserves the existing credential and settings.
Save-DataJudConfiguration -Key $settings.DATAJUD_API_KEY -AuthorizedUse $true
Assert-Contract ($persisted -ceq [Convert]::ToBase64String([IO.File]::ReadAllBytes($script:HmlEnv))) 'Reapply changed profile'
$argsCompose = Get-HmlComposeArgs $settings
Assert-Contract ($argsCompose[$argsCompose.IndexOf('--env-file') + 1] -ceq $script:HmlEnv) 'Wrong env file'
Assert-Contract ($argsCompose[$argsCompose.IndexOf('--project-name') + 1] -ceq $project) 'Wrong project'
# Check fail-closed startup with synthetic local API responses, never a provider.
function Invoke-WebRequest { return @{Content='{"sources":{"datajud":{"enabled":false}}}'} }
$denied = $false
try { Assert-HmlDataJudState $settings } catch { $denied = $true }
Assert-Contract $denied 'Startup silently accepted activation drift'
function Invoke-WebRequest { return @{Content='{"sources":{"datajud":{"enabled":true}}}'} }
Assert-HmlDataJudState $settings
foreach ($missing in @('DATAJUD_AUTHORIZED_USE','DATAJUD_API_KEY')) {
    $invalid = $settings.Clone()
    $invalid[$missing] = ''
    $denied = $false
    try { Assert-HmlDataJudState $invalid } catch { $denied = $true }
    Assert-Contract $denied 'Startup accepted incomplete persisted activation'
}
$composeChecked = $false
if ($CheckCompose) {
    $raw = & docker @argsCompose config --format json 2>$null
    Assert-Contract ($LASTEXITCODE -eq 0) 'Compose rendering failed'
    $config = ($raw -join "`n") | ConvertFrom-Json
    foreach ($service in @('api','worker-1','worker-2','scheduler')) {
        $environment = $config.services.$service.environment
        Assert-Contract ($environment.DATAJUD_ENABLED -eq 'true' -and $environment.DATAJUD_AUTHORIZED_USE -eq 'true') 'Receiver flags differ from persistent profile'
        if ($service -like 'worker-*') {
            Assert-Contract ($environment.DATAJUD_API_KEY -ceq 'synthetic-datajud-secret-123456') 'Worker key missing'
        } else {
            Assert-Contract (-not $environment.DATAJUD_API_KEY) 'Key escaped worker boundary'
        }
    }
    Assert-Contract ($config.name -ceq $project) 'Compose selected another project'
    $composeChecked = $true
}
@{status='pass'; synthetic=$true; new_profile_safe=$true; authorized_save=$true; reopening=$true; runtime_replacement=$true; profile_byte_preserved=$true; ambient_isolation=$true; project_selection=$true; startup_drift_rejected=$true; compose_checked=$composeChecked} | ConvertTo-Json -Compress
