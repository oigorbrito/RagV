$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'homologacao-common.ps1')
Add-Type -AssemblyName System.Windows.Forms
try {
    Initialize-HmlPaths
    if (-not (Test-Path $script:HmlEnv)) { throw 'Abra o RagV Homologação uma vez antes de configurar o DataJud.' }
    $settings = Get-HmlSettings
    $form = New-Object Windows.Forms.Form
    $form.Text = 'Configuração DataJud — RagV Homologação'
    $form.Size = New-Object Drawing.Size(640,330)
    $form.StartPosition = 'CenterScreen'
    $form.FormBorderStyle = 'FixedDialog'
    $form.MaximizeBox = $false
    $link = New-Object Windows.Forms.LinkLabel
    $link.Text = 'Obter a chave pública vigente na fonte oficial do CNJ'
    $link.SetBounds(20,20,580,30)
    $link.Add_LinkClicked({ Start-Process 'https://www.cnj.jus.br/sistemas/datajud/api-publica/' })
    $form.Controls.Add($link)
    $label = New-Object Windows.Forms.Label
    $label.Text = 'Cole a chave vigente. Nenhuma consulta será enviada pela configuração.'
    $label.SetBounds(20,60,580,35)
    $form.Controls.Add($label)
    $keyBox = New-Object Windows.Forms.TextBox
    $keyBox.UseSystemPasswordChar = $true
    $keyBox.SetBounds(20,100,580,26)
    $form.Controls.Add($keyBox)
    $optin = New-Object Windows.Forms.CheckBox
    $optin.Text = 'Confirmo finalidade e uso autorizados pelas regras vigentes do CNJ.'
    $optin.SetBounds(20,145,580,35)
    $form.Controls.Add($optin)
    $status = New-Object Windows.Forms.Label
    $status.SetBounds(20,190,580,30)
    $form.Controls.Add($status)
    $save = New-Object Windows.Forms.Button
    $save.Text = 'Salvar e ativar'
    $save.SetBounds(20,235,150,32)
    $form.Controls.Add($save)
    $save.Add_Click({
        try {
            if (-not $optin.Checked) { throw 'Confirme o uso autorizado antes de ativar.' }
            $key = $keyBox.Text.Trim() -replace '^APIKey\s+', ''
            if ($key -notmatch '^[A-Za-z0-9_+/=:-]{16,2048}$') { throw 'Chave vazia ou formato inválido. Confira a fonte oficial do CNJ.' }
            $save.Enabled = $false
            $lines = @(Get-Content -LiteralPath $script:HmlEnv -Encoding UTF8)
            $new = @($lines | Where-Object { $_ -notmatch '^DATAJUD_(API_KEY|ENABLED|AUTHORIZED_USE)=' })
            $new += @('DATAJUD_ENABLED=true','DATAJUD_AUTHORIZED_USE=true',"DATAJUD_API_KEY=$key")
            $tmp = "$($script:HmlEnv).new"
            $new | Set-Content -LiteralPath $tmp -Encoding ASCII
            Set-HmlPrivatePath $tmp
            Move-Item -LiteralPath $tmp -Destination $script:HmlEnv -Force
            $key = $null
            $keyBox.Clear()
            $script:HmlStatusLabel = $status
            $compose = Get-HmlComposeArgs $settings
            $null = Invoke-HmlDocker -Stage 'Aplicando configuração DataJud autorizada' -DockerArgs ($compose + @('up','-d','--no-build','--no-deps','--force-recreate','api','worker-1','worker-2','scheduler'))
            $script:HmlStatusLabel = $null
            $status.Text = 'DataJud configurado. Nenhuma consulta enviada.'
            [Windows.Forms.MessageBox]::Show('DataJud ativado. A chave fica somente nos workers. Nenhuma consulta foi enviada.', 'Configuração concluída', 'OK', 'Information') | Out-Null
            $form.Close()
        } catch {
            $save.Enabled = $true
            [Windows.Forms.MessageBox]::Show($_.Exception.Message, 'Configuração DataJud — atenção', 'OK', 'Error') | Out-Null
        }
    })
    [void]$form.ShowDialog()
} catch {
    [Windows.Forms.MessageBox]::Show($_.Exception.Message, 'RagV Homologação — atenção', 'OK', 'Error') | Out-Null
    exit 1
}
