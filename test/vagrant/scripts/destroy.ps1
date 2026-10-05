$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
vagrant destroy -f
