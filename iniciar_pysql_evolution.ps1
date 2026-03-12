#Requires -Version 5.1
<#
.SYNOPSIS
  Orquestrador: ativa venv, garante política de execução, verifica/inicia Docker e roda o scheduler PySQL + Evolution.
.DESCRIPTION
  Execute este script em vez de "python scheduler_pysql_evolution.py" para:
  1. Ajustar ExecutionPolicy (RemoteSigned, CurrentUser) se necessário
  2. Ir para a pasta do projeto e ativar a venv
  3. Verificar se o Docker está ativo; se não, iniciar e aguardar normalizar
  4. Registrar webhook na Evolution (se EVOLUTION_WEBHOOK_AUTO_REGISTER=true no .env)
  5. Rodar scheduler_pysql_evolution.py (e servidor webhook em thread)
.EXAMPLE
  PS> .\iniciar_pysql_evolution.ps1
#>

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " Orquestrador PySQL + Evolution API" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# 1) ExecutionPolicy (só CurrentUser, sem elevação)
try {
    $current = Get-ExecutionPolicy -Scope CurrentUser -ErrorAction SilentlyContinue
    if ($current -eq "Restricted" -or $current -eq "Undefined") {
        Write-Host "[1/5] Ajustando politica de execucao (RemoteSigned, CurrentUser)..." -ForegroundColor Yellow
        Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser -Force
        Write-Host "      OK." -ForegroundColor Green
    } else {
        Write-Host "[1/5] Politica de execucao ja permitida para este usuario." -ForegroundColor Green
    }
} catch {
    Write-Host "[1/5] Aviso: nao foi possivel alterar ExecutionPolicy. Continuando..." -ForegroundColor Yellow
}

# 2) Ativar venv
$venvActivate = Join-Path $ProjectRoot ".venv\Scripts\Activate.ps1"
if (-not (Test-Path $venvActivate)) {
    Write-Host "[2/5] ERRO: venv nao encontrada em .venv\Scripts\Activate.ps1" -ForegroundColor Red
    exit 1
}
Write-Host "[2/5] Ativando venv..." -ForegroundColor Yellow
. $venvActivate
Write-Host "      OK." -ForegroundColor Green

# 3) Docker: verificar e, se desligado, iniciar e aguardar
Write-Host "[3/5] Verificando Docker..." -ForegroundColor Yellow
$dockerOk = $false
try {
    $null = docker info 2>&1
    if ($LASTEXITCODE -eq 0) { $dockerOk = $true }
} catch {}

if (-not $dockerOk) {
    $dockerPaths = @(
        "${Env:ProgramFiles}\Docker\Docker\Docker Desktop.exe",
        "${Env:ProgramFiles(x86)}\Docker\Docker\Docker Desktop.exe"
    )
    $dockerExe = $null
    foreach ($p in $dockerPaths) {
        if (Test-Path $p) { $dockerExe = $p; break }
    }
    if ($dockerExe) {
        Write-Host "      Docker nao estava em execucao. Iniciando Docker Desktop..." -ForegroundColor Yellow
        Start-Process -FilePath $dockerExe -WindowStyle Hidden
        $maxWait = 120
        $waited = 0
        while ($waited -lt $maxWait) {
            Start-Sleep -Seconds 5
            $waited += 5
            try {
                $null = docker info 2>&1
                if ($LASTEXITCODE -eq 0) {
                    $dockerOk = $true
                    Write-Host "      Docker pronto apos ${waited}s." -ForegroundColor Green
                    break
                }
            } catch {}
            Write-Host "      Aguardando Docker... ${waited}s" -ForegroundColor Gray
        }
        if (-not $dockerOk) {
            Write-Host "      Aviso: timeout aguardando Docker. Continuando mesmo assim." -ForegroundColor Yellow
        }
    } else {
        Write-Host "      Docker Desktop nao encontrado (opcional). Continuando." -ForegroundColor Gray
    }
} else {
    Write-Host "      Docker ja esta ativo." -ForegroundColor Green
}

# 4) Registrar webhook na Evolution (se .env tiver EVOLUTION_WEBHOOK_AUTO_REGISTER=true)
Write-Host "[4/5] Verificando/registrando webhook na Evolution API..." -ForegroundColor Yellow
& (Join-Path $ProjectRoot ".venv\Scripts\python.exe") (Join-Path $ProjectRoot "evolution_api\registrar_webhook.py")
if ($LASTEXITCODE -ne 0) { Write-Host "      Aviso: registro do webhook falhou. Continuando." -ForegroundColor Yellow }
else { Write-Host "      OK." -ForegroundColor Green }

# 5) Rodar o scheduler (e webhook de comando por @ no WhatsApp, se habilitado)
Write-Host "[5/5] Iniciando scheduler PySQL + Evolution (e webhook)..." -ForegroundColor Yellow
Write-Host "============================================================" -ForegroundColor Cyan
& (Join-Path $ProjectRoot ".venv\Scripts\python.exe") (Join-Path $ProjectRoot "scheduler_pysql_evolution.py")
exit $LASTEXITCODE
