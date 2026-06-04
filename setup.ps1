# Instala dependencias no Python que voce usa no VS Code / terminal
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$py = $null
if (Test-Path ".\.venv\Scripts\python.exe") {
    $py = ".\.venv\Scripts\python.exe"
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $py = "py -3"
} else {
    $py = "python"
}

Write-Host "Usando: $py"
& $py -m pip install --upgrade pip
& $py -m pip install -r requirements.txt
Write-Host "Indicadores: python 1_Coleta_Dados/coletar_indicadores.py (yfinance; FRED opcional no .env)"

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Criado .env — coloque OILPRICE_API_TOKEN antes de coletar petroleo."
}

Write-Host "Setup concluido."
