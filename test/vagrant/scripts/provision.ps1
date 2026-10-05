# Reaplica provisionamento (Chrome / arquivos de teste) sem recriar a VM
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
vagrant provision
