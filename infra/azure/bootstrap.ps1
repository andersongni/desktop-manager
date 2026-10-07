# Bootstrap da VM de teste — baixado/inline pela Custom Script Extension (roda como SYSTEM).
$ErrorActionPreference = 'Stop'

$repo = $env:DM_GITHUB_REPO
if (-not $repo) { $repo = 'andersongni/desktop-manager' }

$dest = 'C:\DesktopManager-release'
$publicDesk = 'C:\Users\Public\Desktop'
New-Item -ItemType Directory -Force -Path $dest | Out-Null

$api = "https://api.github.com/repos/$repo/releases/latest"
$rel = Invoke-RestMethod -Uri $api -Headers @{ 'User-Agent' = 'DesktopManager-AzureBootstrap' }
$asset = $rel.assets |
  Where-Object { $_.name -like 'desktop-manager-windows-x64-*.zip' } |
  Select-Object -First 1
if (-not $asset) {
  throw "Asset zip nao encontrado em https://github.com/$repo/releases/latest"
}

$zip = Join-Path $env:TEMP $asset.name
Write-Host "Baixando $($asset.name)..."
Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $zip
Expand-Archive -Path $zip -DestinationPath $dest -Force

$note = @"
Desktop Manager — teste na Azure
================================
Release: $($rel.tag_name)
Pasta:   $dest

1. Abra C:\DesktopManager-release
2. Execute INSTALAR.cmd (ou INSTALAR.vbs)
3. Use ADMINISTRAR.cmd para configurar
4. Reinicie a sessao / VM para testar startup e auto-update

Dica: publique uma tag vX.Y.Z no GitHub para gerar release nova e validar o updater.
"@
Set-Content -Path (Join-Path $publicDesk 'LER-DesktopManager.txt') -Value $note -Encoding UTF8

# Atalho no Desktop público
$Wsh = New-Object -ComObject WScript.Shell
$lnk = $Wsh.CreateShortcut((Join-Path $publicDesk 'DesktopManager-release.lnk'))
$lnk.TargetPath = $dest
$lnk.Save()

Write-Host "Bootstrap OK: $dest ($($rel.tag_name))"
