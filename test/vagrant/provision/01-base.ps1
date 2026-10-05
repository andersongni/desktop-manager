$ErrorActionPreference = "Stop"
Write-Host "==> [01-base] Preparando Windows 11 para testes do Desktop Manager"

# Política de execução para scripts locais
Set-ExecutionPolicy Bypass -Scope LocalMachine -Force -ErrorAction SilentlyContinue

# Timezone BR (opcional; ignore falha)
try {
    Set-TimeZone -Id "E. South America Standard Time" -ErrorAction Stop
} catch {
    Write-Host "Timezone não alterado: $($_.Exception.Message)"
}

# Chocolatey
if (-not (Get-Command choco -ErrorAction SilentlyContinue)) {
    Write-Host "Instalando Chocolatey..."
    [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
    Invoke-Expression ((New-Object System.Net.WebClient).DownloadString("https://community.chocolatey.org/install.ps1"))
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
                [System.Environment]::GetEnvironmentVariable("Path", "User")
} else {
    Write-Host "Chocolatey já instalado."
}

# Ferramentas úteis para inspecionar o Desktop Manager
choco upgrade chocolatey -y --no-progress | Out-Null
choco install -y --no-progress 7zip notepadplusplus

# Pastas de teste
New-Item -ItemType Directory -Force -Path "C:\dm-test\desktop" | Out-Null
New-Item -ItemType Directory -Force -Path "C:\dm-test\logs" | Out-Null
New-Item -ItemType Directory -Force -Path "C:\Users\vagrant\Desktop\dm-sample" | Out-Null

Write-Host "==> [01-base] Concluído"
