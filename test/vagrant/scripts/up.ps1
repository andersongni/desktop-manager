# Sobe a VM de testes (Windows 11 + Chrome)
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

Write-Host "Provider: VirtualBox (padrao). Para Hyper-V: `$env:VAGRANT_DEFAULT_PROVIDER='hyperv'"
Write-Host "Memoria:  `$env:DM_VM_MEMORY (padrao 8192)  CPUs: `$env:DM_VM_CPUS (padrao 2)"
Write-Host ""

if (-not (Get-Command vagrant -ErrorAction SilentlyContinue)) {
    throw "Vagrant nao encontrado no PATH. Instale: https://developer.hashicorp.com/vagrant/install"
}

vagrant up
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host ""
Write-Host "VM pronta. RDP: vagrant rdp   |   Login: vagrant / vagrant"
