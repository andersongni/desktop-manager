# Bootstrap da VM de teste — baixado/inline pela Custom Script Extension (roda como SYSTEM).
[CmdletBinding()]
param(
  [string]$AdminUsername = '',
  [string]$AdminPassword = ''
)

$ErrorActionPreference = 'Stop'

if (-not $AdminUsername) { $AdminUsername = $env:DM_ADMIN_USERNAME }
if (-not $AdminPassword) { $AdminPassword = $env:DM_ADMIN_PASSWORD }
if (-not $AdminPassword -and $env:DM_ADMIN_PASSWORD_B64) {
  $AdminPassword = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($env:DM_ADMIN_PASSWORD_B64))
}
if (-not $AdminUsername) { $AdminUsername = 'dmadmin' }

function Set-LocalePtBr {
  Write-Host 'Configurando idioma Português (Brasil)...'
  Set-TimeZone -Id 'E. South America Standard Time' -ErrorAction SilentlyContinue
  try { Set-WinHomeLocation -GeoId 32 } catch { Write-Warning "GeoId: $_" }

  $hasInstallLanguage = Get-Command Install-Language -ErrorAction SilentlyContinue
  if ($hasInstallLanguage) {
    $installed = @(Get-InstalledLanguage -ErrorAction SilentlyContinue | ForEach-Object { $_.LanguageId })
    if ($installed -notcontains 'pt-BR') {
      Write-Host 'Instalando Language Pack pt-BR (pode demorar)...'
      Install-Language -Language pt-BR -CopyToSettings
    } else {
      Write-Host 'Language Pack pt-BR já instalado.'
    }
  } else {
    Write-Warning 'Install-Language indisponível — aplicando locale básico.'
  }

  try { Set-WinSystemLocale -SystemLocale pt-BR } catch { Write-Warning "SystemLocale: $_" }
  try { Set-WinUILanguageOverride -Language pt-BR } catch { Write-Warning "UILanguage: $_" }
  try {
    $list = New-WinUserLanguageList -Language pt-BR
    Set-WinUserLanguageList -LanguageList $list -Force
  } catch { Write-Warning "UserLanguageList: $_" }
  try { Set-Culture -CultureInfo pt-BR } catch { Write-Warning "Culture: $_" }

  $defaultHive = 'HKLM\TempDefaultUser'
  $ntuser = 'C:\Users\Default\NTUSER.DAT'
  if (Test-Path $ntuser) {
    reg load $defaultHive $ntuser | Out-Null
    try {
      reg add "$defaultHive\Control Panel\International" /v LocaleName /t REG_SZ /d 'pt-BR' /f | Out-Null
      reg add "$defaultHive\Control Panel\Desktop" /v PreferredUILanguages /t REG_MULTI_SZ /d 'pt-BR' /f | Out-Null
    } finally {
      reg unload $defaultHive | Out-Null
    }
  }

  Write-Host 'Locale pt-BR aplicado (reinício recomendado para UI completa).'
}

function Enable-LocalAutoLogon {
  param(
    [Parameter(Mandatory)][string]$Username,
    [Parameter(Mandatory)][string]$Password
  )

  Write-Host "Configurando conta local '$Username' com logon automático (sem prompt de senha)..."

  try {
    $user = Get-LocalUser -Name $Username -ErrorAction Stop
    Set-LocalUser -Name $Username -PasswordNeverExpires $true -ErrorAction SilentlyContinue
    if ($user.Enabled -ne $true) {
      Enable-LocalUser -Name $Username -ErrorAction SilentlyContinue
    }
  } catch {
    Write-Warning "LocalUser '$Username': $_"
  }

  # Não exigir CTRL+ALT+DEL nem prompt extra de senha no RDP
  $winlogon = 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon'
  New-ItemProperty -Path $winlogon -Name AutoAdminLogon -PropertyType String -Value '1' -Force | Out-Null
  New-ItemProperty -Path $winlogon -Name DefaultUserName -PropertyType String -Value $Username -Force | Out-Null
  New-ItemProperty -Path $winlogon -Name DefaultPassword -PropertyType String -Value $Password -Force | Out-Null
  New-ItemProperty -Path $winlogon -Name DefaultDomainName -PropertyType String -Value $env:COMPUTERNAME -Force | Out-Null
  New-ItemProperty -Path $winlogon -Name AutoLogonCount -PropertyType String -Value '999' -Force | Out-Null
  New-ItemProperty -Path $winlogon -Name DisableCAD -PropertyType DWord -Value 1 -Force | Out-Null

  $rdpTcp = 'HKLM:\SYSTEM\CurrentControlSet\Control\Terminal Server\WinStations\RDP-Tcp'
  if (Test-Path $rdpTcp) {
    New-ItemProperty -Path $rdpTcp -Name fPromptForPassword -PropertyType DWord -Value 0 -Force | Out-Null
  }

  # Política: permitir credenciais salvas do cliente RDP
  $ts = 'HKLM:\SOFTWARE\Policies\Microsoft\Windows NT\Terminal Services'
  if (-not (Test-Path $ts)) { New-Item -Path $ts -Force | Out-Null }
  New-ItemProperty -Path $ts -Name fPromptForPassword -PropertyType DWord -Value 0 -Force | Out-Null
  New-ItemProperty -Path $ts -Name fDisablePasswordSaving -PropertyType DWord -Value 0 -Force | Out-Null

  Write-Host 'Auto-logon local habilitado.'
}

Set-LocalePtBr

if ($AdminPassword) {
  Enable-LocalAutoLogon -Username $AdminUsername -Password $AdminPassword
} else {
  Write-Warning 'DM_ADMIN_PASSWORD ausente — auto-logon não configurado.'
}

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
Desktop Manager — teste na Azure (Windows 11 pt-BR)
===================================================
Release: $($rel.tag_name)
Pasta:   $dest
Conta:   $AdminUsername (local, auto-logon)

1. Abra C:\DesktopManager-release
2. Execute INSTALAR.cmd (ou INSTALAR.vbs)
3. Use ADMINISTRAR.cmd para configurar
4. Reinicie a sessao / VM para testar startup e auto-update

Idioma: Português (Brasil). Conta local com logon automático (sem pedir senha na tela de login).
"@
Set-Content -Path (Join-Path $publicDesk 'LER-DesktopManager.txt') -Value $note -Encoding UTF8

$Wsh = New-Object -ComObject WScript.Shell
$lnk = $Wsh.CreateShortcut((Join-Path $publicDesk 'DesktopManager-release.lnk'))
$lnk.TargetPath = $dest
$lnk.Save()

Write-Host "Bootstrap OK: $dest ($($rel.tag_name))"
