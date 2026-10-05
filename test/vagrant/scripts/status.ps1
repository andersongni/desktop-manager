$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
vagrant status
vagrant winrm -c "Write-Host ('Chrome: ' + (Test-Path 'C:\Program Files\Google\Chrome\Application\chrome.exe'))"
