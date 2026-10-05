$ErrorActionPreference = "Stop"
Write-Host "==> [02-chrome] Instalando Google Chrome"

$env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
            [System.Environment]::GetEnvironmentVariable("Path", "User")

function Test-ChromeInstalled {
    $paths = @(
        "${env:ProgramFiles}\Google\Chrome\Application\chrome.exe",
        "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe"
    )
    foreach ($p in $paths) {
        if (Test-Path $p) { return $true }
    }
    return $false
}

if (Test-ChromeInstalled) {
    Write-Host "Google Chrome já está instalado."
    exit 0
}

# Preferência: Chocolatey (silencioso e versionado)
if (Get-Command choco -ErrorAction SilentlyContinue) {
    Write-Host "Instalando via Chocolatey (googlechrome)..."
    choco install googlechrome -y --no-progress --ignore-checksums
}

if (-not (Test-ChromeInstalled)) {
    Write-Host "Fallback: instalador oficial offline do Chrome..."
    $installer = Join-Path $env:TEMP "ChromeStandaloneSetup64.exe"
    $url = "https://dl.google.com/chrome/install/latest/chrome_installer.exe"
    Invoke-WebRequest -Uri $url -OutFile $installer -UseBasicParsing
    Start-Process -FilePath $installer -ArgumentList "/silent", "/install" -Wait
    Remove-Item $installer -Force -ErrorAction SilentlyContinue
}

if (-not (Test-ChromeInstalled)) {
    throw "Falha ao instalar Google Chrome"
}

$chrome = (Get-ChildItem -Path "${env:ProgramFiles}\Google\Chrome\Application\chrome.exe","${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe" -ErrorAction SilentlyContinue | Select-Object -First 1).FullName
Write-Host "Chrome instalado em: $chrome"
Write-Host "==> [02-chrome] Concluído"
