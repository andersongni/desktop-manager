<#
.SYNOPSIS
  Mantém uma Subscription POC, cancela a outra e sobe a VM de teste.
#>
[CmdletBinding()]
param(
  [string]$KeepSubscriptionId = 'cfecccfd-204d-45d0-973c-34f092cd3940',
  [string]$CancelSubscriptionId = '8ddb9e6a-743d-409e-98f9-b06c618ca29b',
  [string]$ResourceGroup = 'rg-desktop-manager-test',
  [string]$Location = 'eastus',
  [string]$NamePrefix = 'dmtest',
  [string]$AdminUsername = 'dmadmin',
  [string]$VmSize = 'Standard_B2ats_v2'
)

$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "Usando subscription: $KeepSubscriptionId"
az account set --subscription $KeepSubscriptionId
az account show --query "{name:name,id:id,state:state}" -o json

Write-Host "Cancelando subscription duplicada: $CancelSubscriptionId"
az account subscription cancel --id $CancelSubscriptionId --yes 2>&1
if ($LASTEXITCODE -ne 0) {
  # Fallback REST
  az rest --method post `
    --url "https://management.azure.com/subscriptions/$CancelSubscriptionId/providers/Microsoft.Subscription/cancel?api-version=2021-10-01" `
    --body '{}' 2>&1
}

# Senha sem caracteres que quebram shell (& $ %)
$pwd = 'DmTest-' + ([guid]::NewGuid().ToString('N').Substring(0, 12)) + '-Aa1'
$paramFile = Join-Path $env:TEMP 'dm-azure-params.json'

try {
  $myIp = (Invoke-RestMethod -Uri 'https://api.ipify.org' -TimeoutSec 20).Trim()
  $rdp = "$myIp/32"
} catch {
  $rdp = '*'
}

@{
  namePrefix               = @{ value = $NamePrefix }
  adminUsername            = @{ value = $AdminUsername }
  adminPassword            = @{ value = $pwd }
  vmSize                   = @{ value = $VmSize }
  allowedRdpSource         = @{ value = $rdp }
  autoShutdownTime         = @{ value = '2200' }
  bootstrapDesktopManager  = @{ value = $true }
} | ConvertTo-Json -Depth 5 | Set-Content -Path $paramFile -Encoding utf8

Write-Host "Criando RG $ResourceGroup em $Location (RDP=$rdp)..."
az group create --name $ResourceGroup --location $Location --output none

Write-Host 'Deploy Bicep...'
az deployment group create `
  --resource-group $ResourceGroup `
  --template-file (Join-Path $here 'main.bicep') `
  --parameters "@$paramFile" `
  --name dmtest-deploy `
  --output none

Remove-Item $paramFile -Force -ErrorAction SilentlyContinue

$ip = az network public-ip show -g $ResourceGroup -n "$NamePrefix-pip" --query ipAddress -o tsv

Write-Host ''
Write-Host '=== PRONTO ===' -ForegroundColor Green
Write-Host "keptSubscription=$KeepSubscriptionId"
Write-Host "cancelledSubscription=$CancelSubscriptionId"
Write-Host "resourceGroup=$ResourceGroup"
Write-Host "adminUser=$AdminUsername"
Write-Host "adminPassword=$pwd"
Write-Host "publicIp=$ip"
Write-Host "rdp=mstsc /v:$ip"
Write-Host "package=C:\DesktopManager-release"
