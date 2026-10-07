<#
.SYNOPSIS
  Sobe a VM Windows de teste do Desktop Manager na Azure (Bicep / free-tier friendly).

.EXAMPLE
  .\deploy.ps1
  .\deploy.ps1 -Location eastus -VmSize Standard_B2ats_v2
  .\deploy.ps1 -AllowedRdpSource '203.0.113.10/32'
#>
[CmdletBinding()]
param(
  [string]$ResourceGroup = 'rg-desktop-manager-test',
  [string]$Location = 'eastus',
  [string]$NamePrefix = 'dmtest',
  [string]$AdminUsername = 'dmadmin',
  [string]$AdminPassword = '',
  [string]$VmSize = 'Standard_D2s_v4',
  [string]$AllowedRdpSource = '',
  [string]$AutoShutdownTime = '2200',
  # CSE do Bicep baixa bootstrap do GitHub — desligado por padrão.
  # O deploy aplica o bootstrap.ps1 local (pt-BR + auto-logon + app) via run-command.
  [switch]$UseGithubBootstrap,
  [switch]$SkipLocalBootstrap,
  # Padrão: abre o RDP já com credencial da conta local (sem pedir senha no cliente)
  [bool]$OpenRdp = $true
)

$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path

function Assert-AzCli {
  if (-not (Get-Command az -ErrorAction SilentlyContinue)) {
    throw 'Azure CLI (az) não encontrado. Instale: https://learn.microsoft.com/cli/azure/install-azure-cli'
  }
  $account = az account show 2>$null | ConvertFrom-Json
  if (-not $account) {
    Write-Host 'Fazendo login na Azure...'
    az login | Out-Null
    $account = az account show | ConvertFrom-Json
  }
  Write-Host "Assinatura: $($account.name) ($($account.id))"
}

function Get-MyPublicIpCidr {
  try {
    $ip = (Invoke-RestMethod -Uri 'https://api.ipify.org' -TimeoutSec 15).Trim()
    if ($ip -match '^\d+\.\d+\.\d+\.\d+$') { return "$ip/32" }
  } catch {
    Write-Warning "Não foi possível detectar seu IP público: $_"
  }
  return '*'
}

Assert-AzCli

if (-not $AllowedRdpSource) {
  $AllowedRdpSource = Get-MyPublicIpCidr
  Write-Host "RDP liberado para: $AllowedRdpSource"
}

if ($AdminPassword) {
  $plain = $AdminPassword
} else {
  # Gera senha forte automaticamente — não interrompe o deploy pedindo senha.
  # A conta local na VM fica com auto-logon; o RDP usa cmdkey no cliente.
  $plain = 'Dm-' + [guid]::NewGuid().ToString('N').Substring(0, 10) + '-Aa1!'
  Write-Host "Senha da conta local gerada automaticamente (salva no Credential Manager ao abrir o RDP)."
}
if ([string]::IsNullOrWhiteSpace($plain) -or $plain.Length -lt 12) {
  throw 'Senha inválida (mínimo 12 caracteres).'
}

Write-Host "Criando resource group $ResourceGroup em $Location..."
az group create --name $ResourceGroup --location $Location --output none

# Arquivo de parâmetros evita que caracteres especiais da senha quebrem o az.cmd (cmd.exe)
$paramsPath = Join-Path $env:TEMP ("dm-azure-params-{0}.json" -f [guid]::NewGuid())
$paramsObj = [ordered]@{
  namePrefix               = @{ value = $NamePrefix }
  adminUsername            = @{ value = $AdminUsername }
  adminPassword            = @{ value = $plain }
  vmSize                   = @{ value = $VmSize }
  allowedRdpSource         = @{ value = $AllowedRdpSource }
  autoShutdownTime         = @{ value = $AutoShutdownTime }
  bootstrapDesktopManager  = @{ value = [bool]$UseGithubBootstrap }
}
$paramsObj | ConvertTo-Json -Depth 5 | Set-Content -Path $paramsPath -Encoding utf8

try {
  Write-Host 'Deploy Bicep (pode levar alguns minutos)...'
  $deployJson = az deployment group create `
    --resource-group $ResourceGroup `
    --template-file (Join-Path $here 'main.bicep') `
    --parameters "@$paramsPath" `
    --query properties.outputs `
    --output json
  if ($LASTEXITCODE -ne 0) {
    throw "Deploy Bicep falhou (exit $LASTEXITCODE). Veja o erro do Azure CLI acima."
  }
  if ($deployJson) { $deployJson | Out-Host }
} finally {
  Remove-Item -LiteralPath $paramsPath -Force -ErrorAction SilentlyContinue
  $paramsObj = $null
}

$ip = az network public-ip show `
  --resource-group $ResourceGroup `
  --name "$NamePrefix-pip" `
  --query ipAddress -o tsv
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($ip)) {
  $plain = $null
  throw "VM/IP nao encontrados - o deploy provavelmente nao concluiu. Resource group: $ResourceGroup"
}

if (-not $SkipLocalBootstrap) {
  Write-Host 'Aplicando bootstrap local (pt-BR, conta local com auto-logon, Desktop Manager)...'
  $pwdB64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($plain))
  $wrapPath = Join-Path $env:TEMP ("dm-bootstrap-wrap-{0}.ps1" -f [guid]::NewGuid())
  $bootPath = Join-Path $here 'bootstrap.ps1'
  # Script único enviado à VM (não pode referenciar caminhos do PC local)
  $header = @"
`$ErrorActionPreference = 'Stop'
`$env:DM_ADMIN_USERNAME = '$AdminUsername'
`$env:DM_ADMIN_PASSWORD_B64 = '$pwdB64'
`$env:DM_GITHUB_REPO = 'andersongni/desktop-manager'
"@
  $header + "`n" + (Get-Content -LiteralPath $bootPath -Raw) |
    Set-Content -Path $wrapPath -Encoding utf8
  try {
    az vm run-command invoke `
      --resource-group $ResourceGroup `
      --name "$NamePrefix-vm" `
      --command-id RunPowerShellScript `
      --scripts "@$wrapPath" `
      --output none
    if ($LASTEXITCODE -ne 0) {
      throw "Bootstrap local falhou (exit $LASTEXITCODE)."
    }
    Write-Host 'Bootstrap local OK. Reiniciando VM para aplicar auto-logon/idioma...'
    az vm restart --resource-group $ResourceGroup --name "$NamePrefix-vm" --no-wait | Out-Null
    Start-Sleep -Seconds 35
  } finally {
    Remove-Item -LiteralPath $wrapPath -Force -ErrorAction SilentlyContinue
  }
}

# Arquivo .rdp local (sem senha no arquivo) — credencial vai para o Credential Manager
$rdpPath = Join-Path $here "$NamePrefix.rdp"
@(
  "full address:s:$ip"
  "username:s:$AdminUsername"
  'prompt for credentials:i:0'
  'authentication level:i:2'
  'negotiate security layer:i:1'
) | Set-Content -Path $rdpPath -Encoding ascii

Write-Host ''
Write-Host '=== VM pronta ===' -ForegroundColor Green
Write-Host "Resource group : $ResourceGroup"
Write-Host "VM size        : $VmSize"
Write-Host "Usuário local  : $AdminUsername (auto-logon na VM)"
Write-Host "IP público     : $ip"
Write-Host "RDP            : mstsc /v:$ip"
Write-Host "Atalho RDP     : $rdpPath"
Write-Host "Pacote         : C:\DesktopManager-release (após o bootstrap)"
Write-Host "Auto-shutdown  : $AutoShutdownTime (E. South America Standard Time)"
Write-Host ''
Write-Host 'Para destruir tudo:  .\destroy.ps1'
Write-Host 'Para só parar (deallocate): az vm deallocate -g $ResourceGroup -n "$NamePrefix-vm"'

# Sempre registra a conta local no Credential Manager deste PC (RDP sem digitar senha)
Write-Host ''
Write-Host "Registrando credencial local '$AdminUsername' para $ip ..."
cmdkey /generic:"TERMSRV/$ip" /user:".\$AdminUsername" /pass:"$plain" | Out-Null
cmdkey /generic:"TERMSRV/$ip" /user:"$AdminUsername" /pass:"$plain" | Out-Null

if ($OpenRdp) {
  Write-Host "Abrindo Remote Desktop para $ip (sem pedir senha)..."
  Start-Process mstsc -ArgumentList "`"$rdpPath`""
}

$plain = $null
