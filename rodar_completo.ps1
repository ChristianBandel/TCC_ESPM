# Fluxo completo: GED + petroleo + preparacao + modelagem
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (Test-Path ".\.venv\Scripts\python.exe") {
    $py = ".\.venv\Scripts\python.exe"
} else {
    $py = "python"
}

$ged = "1_Coleta_Dados\GEDEvent_v25_1.csv"
if (-not (Test-Path $ged)) {
    Write-Error "Arquivo nao encontrado: $ged"
}

Write-Host "=== 1/4 Conflitos (GED) ==="
& $py 1_Coleta_Dados/coletar_conflitos.py --csv $ged

Write-Host "=== 2/5 Indicadores macro ==="
& $py 1_Coleta_Dados/coletar_indicadores.py

Write-Host "=== 3/5 Petroleo (API) ==="
& $py 1_Coleta_Dados/coletar_petroleo.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "Falha na coleta de petroleo. Verifique OILPRICE_API_TOKEN no .env"
    exit $LASTEXITCODE
}

Write-Host "=== 4-5/5 Pipeline ML ==="
& $py executar_pipeline.py --cenario

Write-Host "Concluido. Dataset: dados\processed\dataset_ml.csv"
