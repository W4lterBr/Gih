# Gera o instalador da Confeitaria (interface nova, NSIS) com o motor Python embutido.
#
#   powershell -ExecutionPolicy Bypass -File scripts\gerar-instalador.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\gerar-instalador.ps1 -PularMotor   # reaproveita o motor já gerado
#
# Passos:
#   1. Empacota o motor (motor.spec na raiz do projeto -> dist\confeitaria-motor)
#   2. Copia para src-tauri\motor (vira recurso do instalador; fora do git)
#   3. tauri build -> src-tauri\target\release\bundle\nsis\*.exe
#   4. Copia o instalador para desktop\Output
#
# Sem atualizador automático (decisão da Confeitaria): cada versão nova é um instalador.
param(
    [switch]$PularMotor,
    # Raiz do projeto Python (a interface fica em desktop\)
    [string]$Projeto = (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent)
)
$ErrorActionPreference = "Stop"
$raiz = Split-Path $PSScriptRoot -Parent

# Python: .venv do projeto, senão o lançador "py" do Windows.
$python = Join-Path $Projeto ".venv\Scripts\python.exe"
$pyArgs = @()
if (-not (Test-Path $python)) { $python = "py"; $pyArgs = @("-3") }

if (-not $PularMotor) {
    Write-Host "[1/4] Empacotando o motor..." -ForegroundColor Cyan
    Push-Location $Projeto
    try {
        & $python @pyArgs -m PyInstaller --noconfirm --log-level WARN "motor.spec"
        if ($LASTEXITCODE -ne 0) { throw "PyInstaller falhou ($LASTEXITCODE)" }
    } finally { Pop-Location }
}

Write-Host "[2/4] Copiando o motor para o instalador..." -ForegroundColor Cyan
$origem = Join-Path $Projeto "dist\confeitaria-motor"
if (-not (Test-Path "$origem\confeitaria-motor.exe")) { throw "Motor não encontrado em $origem" }
robocopy $origem (Join-Path $raiz "src-tauri\motor") /MIR /NFL /NDL /NJH /NJS /NP | Out-Null
if ($LASTEXITCODE -ge 8) { throw "robocopy falhou ($LASTEXITCODE)" }

Write-Host "[3/4] Gerando o instalador..." -ForegroundColor Cyan
$env:PATH = "$env:USERPROFILE\.cargo\bin;$env:PATH"
Push-Location $raiz
try {
    npx tauri build
    if ($LASTEXITCODE -ne 0) { throw "tauri build falhou ($LASTEXITCODE)" }
} finally { Pop-Location }

Write-Host "[4/4] Copiando para desktop\Output..." -ForegroundColor Cyan
$saida = Join-Path $raiz "Output"
New-Item -ItemType Directory -Force $saida | Out-Null
Copy-Item (Join-Path $raiz "src-tauri\target\release\bundle\nsis\*.exe") $saida -Force
Get-ChildItem $saida | Format-Table Name, @{n="MB";e={[math]::Round($_.Length/1MB,1)}}
