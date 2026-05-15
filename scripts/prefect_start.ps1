$ErrorActionPreference = "Stop"

$env:PYTHONUTF8 = "1"
$env:PREFECT_API_URL = "http://127.0.0.1:4200/api"
$Dir = $PWD.Path

function Start-Window([string]$cmd) {
    Start-Process powershell -ArgumentList "-NoProfile", "-NoExit", "-Command", "Set-Location '$Dir'; $cmd"
}

Write-Host "==> Iniciando servidor Prefect..."
Start-Window ".venv\Scripts\prefect server start"

Write-Host "==> Aguardando servidor ficar pronto..." -NoNewline
$ready = $false
for ($i = 1; $i -le 30; $i++) {
    Start-Sleep -Seconds 1
    try {
        $null = Invoke-WebRequest -Uri "http://127.0.0.1:4200/api/health" -UseBasicParsing -TimeoutSec 1 -ErrorAction Stop
        $ready = $true
        break
    } catch {}
    Write-Host -NoNewline "."
}
Write-Host ""

if (-not $ready) {
    Write-Error "Timeout: servidor nao iniciou em 30s"
    exit 1
}

Write-Host "==> Servidor pronto."

Write-Host "==> Criando work pool 'local-process'..."
.venv\Scripts\prefect work-pool create local-process --type process 2>&1 | Out-Null
if ($LASTEXITCODE -eq 0) {
    Write-Host "    Criado."
} else {
    Write-Host "    Ja existe, continuando."
}

Write-Host "==> Registrando deployments..."
.venv\Scripts\prefect deploy --all

Write-Host "==> Iniciando worker..."
Start-Window ".venv\Scripts\prefect worker start --pool local-process"

Write-Host ""
Write-Host "======================================"
Write-Host "  Prefect UI: http://localhost:4200"
Write-Host "======================================"
Write-Host ""
Write-Host "Para disparar um run:"
Write-Host "  make prefect-run"
Write-Host "  make prefect-run STEPS=bronze,silver"
