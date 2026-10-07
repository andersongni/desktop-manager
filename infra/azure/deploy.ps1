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
  [switch]$SkipBootstrap,
  [switch]$OpenRdp
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
  $secure = Read-Host -AsSecureString 'Senha do admin da VM (mín. 12 chars, maiúsc/minúsc/número/símbolo)'
  $BSTR = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
  try {
    $plain = [Runtime.InteropServices.Marshal]::PtrToStringAuto($BSTR)
  } finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($BSTR)
  }
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
  bootstrapDesktopManager  = @{ value = (-not $SkipBootstrap) }
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

Write-Host ''
Write-Host '=== VM pronta ===' -ForegroundColor Green
Write-Host "Resource group : $ResourceGroup"
Write-Host "VM size        : $VmSize"
Write-Host "Usuário        : $AdminUsername"
Write-Host "IP público     : $ip"
Write-Host "RDP            : mstsc /v:$ip"
Write-Host "Pacote         : C:\DesktopManager-release (após o bootstrap)"
Write-Host "Auto-shutdown  : $AutoShutdownTime (E. South America Standard Time)"
Write-Host ''
Write-Host 'Para destruir tudo:  .\destroy.ps1'
Write-Host 'Para só parar (deallocate): az vm deallocate -g $ResourceGroup -n "$NamePrefix-vm"'

if ($OpenRdp) {
  Write-Host ''
  Write-Host "Abrindo Remote Desktop para $ip ..."
  cmdkey /generic:"TERMSRV/$ip" /user:"$AdminUsername" /pass:"$plain" | Out-Null
  Start-Process mstsc -ArgumentList "/v:$ip"
}

$plain = $null
