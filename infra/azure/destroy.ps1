<#
.SYNOPSIS
  Remove o resource group da VM de teste (para a cobrança).

.EXAMPLE
  .\destroy.ps1
  .\destroy.ps1 -ResourceGroup rg-desktop-manager-test
#>
[CmdletBinding()]
param(
  [string]$ResourceGroup = 'rg-desktop-manager-test',
  [switch]$Force
)

$ErrorActionPreference = 'Stop'

if (-not (Get-Command az -ErrorAction SilentlyContinue)) {
  throw 'Azure CLI (az) não encontrado.'
}

$exists = az group exists --name $ResourceGroup | ConvertFrom-Json
if (-not $exists) {
  Write-Host "Resource group '$ResourceGroup' não existe."
  return
}

if (-not $Force) {
  $confirm = Read-Host "Apagar TODO o resource group '$ResourceGroup'? (digite sim)"
  if ($confirm -ne 'sim') {
    Write-Host 'Cancelado.'
    return
  }
}

Write-Host "Removendo $ResourceGroup..."
az group delete --name $ResourceGroup --yes --no-wait
Write-Host 'Exclusão iniciada (assíncrona). Em alguns minutos a cobrança de compute/disco para.'
