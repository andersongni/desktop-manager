$ErrorActionPreference = "Stop"
Write-Host "==> [03-ready] Preparando área de trabalho de teste"

$desktop = [Environment]::GetFolderPath("Desktop")
$sampleDir = Join-Path $desktop "dm-sample"
New-Item -ItemType Directory -Force -Path $sampleDir | Out-Null

# Arquivos fictícios para validar o organizador do Desktop Manager
$samples = @{
    "nota-teste.txt"      = "Arquivo de texto para pasta Documentos"
    "planilha-teste.csv"  = "a,b,c`n1,2,3"
    "foto-teste.jpg"      = $null  # placeholder binário mínimo
    "arquivo-teste.zip"   = $null
}

foreach ($name in $samples.Keys) {
    $path = Join-Path $desktop $name
    if (-not (Test-Path $path)) {
        if ($null -eq $samples[$name]) {
            # JPEG/ZIP mínimos inválidos bastam para o organizador mover por extensão
            [System.IO.File]::WriteAllBytes($path, [byte[]](0x00, 0x01, 0x02, 0x03))
        } else {
            Set-Content -Path $path -Value $samples[$name] -Encoding UTF8
        }
    }
}

# Atalho para a pasta sincronizada do projeto
$wsh = New-Object -ComObject WScript.Shell
$lnk = $wsh.CreateShortcut((Join-Path $desktop "desktop-manager.lnk"))
$lnk.TargetPath = "C:\desktop-manager"
$lnk.Save()

$release = "C:\desktop-manager\release\DesktopManager"
if (Test-Path (Join-Path $release "INSTALAR.cmd")) {
    $inst = $wsh.CreateShortcut((Join-Path $desktop "Instalar Desktop Manager.lnk"))
    $inst.TargetPath = Join-Path $release "INSTALAR.cmd"
    $inst.WorkingDirectory = $release
    $inst.Save()
    Write-Host "Release encontrado — atalho de instalação criado na Desktop."
} else {
    Write-Host "Release ainda não gerado no host. Rode 'python scripts\build_release.py' e 'vagrant reload' / re-provision."
}

# README rápido na Desktop
@"
Desktop Manager — VM de teste
=============================
Usuario: vagrant
Senha:   vagrant

1. (No host) Gere o pacote:  python scripts\build_release.py
2. Na VM, abra o atalho 'Instalar Desktop Manager' ou:
   C:\desktop-manager\release\DesktopManager\INSTALAR.cmd
3. Use ADMINISTRAR.cmd para configurar
4. Arquivos de amostra na Desktop servem para testar a organizacao

Chrome: ja instalado
Projeto sincronizado: C:\desktop-manager
"@ | Set-Content -Path (Join-Path $desktop "LEIA-ME-TESTE.txt") -Encoding UTF8

Write-Host "==> [03-ready] VM pronta para testes"
Write-Host "    Usuario/senha: vagrant / vagrant"
Write-Host "    Projeto: C:\desktop-manager"
