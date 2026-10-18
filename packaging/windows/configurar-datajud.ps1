$ErrorActionPreference = 'Stop'
$project = Join-Path $env:LOCALAPPDATA 'RagV-Homologacao\project'
$envFile = Join-Path $project '.env'
$revision = 'a414b2a1d478ccfbf33611a7c40437dd3f90f3b7'
$composeProject = $null
if (-not (Test-Path $envFile)) { throw 'Abra o RagV Homologação ao menos uma vez antes de configurar o DataJud.' }
$composeProject = ((Get-Content -LiteralPath $envFile | Where-Object { $_ -like 'COMPOSE_PROJECT_NAME=*' } | Select-Object -First 1) -replace '^COMPOSE_PROJECT_NAME=','')
if ($composeProject -notmatch '^ragv-hml-[a-f0-9]{12}$') { throw 'Perfil de homologação inválido.' }
Write-Host 'Obtenha manualmente a chave vigente no portal oficial do CNJ: https://www.cnj.jus.br/sistemas/datajud/api-publica/'
Write-Host 'Confirme que a finalidade e o uso pretendido estão autorizados pelas regras vigentes.'
$confirm = Read-Host 'Digite AUTORIZO para habilitar consultas DataJud sob sua responsabilidade'
if ($confirm -cne 'AUTORIZO') { throw 'Configuração cancelada; nenhuma chave foi gravada.' }
$secure = Read-Host 'Chave pública vigente do DataJud' -AsSecureString
$ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try { $key = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr) } finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
if ([string]::IsNullOrWhiteSpace($key) -or $key.Contains("`n") -or $key.Contains("`r")) { throw 'Chave vazia ou inválida.' }
$lines = [System.Collections.Generic.List[string]](Get-Content -LiteralPath $envFile)
foreach ($entry in @(@('DATAJUD_ENABLED','true'),@('DATAJUD_AUTHORIZED_USE','true'),@('DATAJUD_API_KEY',$key))) {
  $name = $entry[0]; $value = $entry[1]; $found = $false
  for ($i=0; $i -lt $lines.Count; $i++) { if ($lines[$i] -match "^$name=") { $lines[$i] = "$name=$value"; $found=$true; break } }
  if (-not $found) { $lines.Add("$name=$value") }
}
$lines | Set-Content -LiteralPath $envFile -Encoding ascii
$key = $null; $secure.Dispose()
foreach ($name in @('COMPOSE_FILE','COMPOSE_PROJECT_NAME','POSTGRES_PASSWORD','PGPORT','RPY_API_PORT','RPY_BEARER_TOKENS','RPY_TENANT_PROCESSES','RPY_OPS_TOKEN','JUDIT_WEBHOOK_TOKEN','JUDIT_WEBHOOK_TENANT_ID','JUDIT_API_KEY','JUDIT_CALLBACK_URL','DATAJUD_ENABLED','DATAJUD_AUTHORIZED_USE','DATAJUD_API_KEY','DATAJUD_BASE_URL','ANTHROPIC_API_KEY','OPENAI_API_KEY')) { [Environment]::SetEnvironmentVariable($name, $null, 'Process') }
Push-Location $project
try {
  docker compose --project-name $composeProject -f compose.yaml -f compose.homologacao.yaml up -d --no-build --no-deps --force-recreate api worker-1 worker-2 scheduler
  if ($LASTEXITCODE -ne 0) { throw 'Falha ao recriar workers DataJud.' }
} finally { Pop-Location }
Write-Host 'DataJud ativado; nenhuma consulta foi enviada. Credencial configurada apenas no ambiente dos workers.'
Read-Host 'Pressione Enter para fechar' | Out-Null
