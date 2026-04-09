#Requires -Version 5.1
<#
.SYNOPSIS
  Orquestrador: ativa venv, garante política de execução, verifica/inicia Docker e roda o scheduler PySQL + Evolution.
.DESCRIPTION
  Execute este script em vez de "python scheduler_pysql_evolution.py" para:
  1. Ajustar ExecutionPolicy (RemoteSigned, CurrentUser) se necessário
  2. Ir para a pasta do projeto e ativar a venv
  3. Se o Docker Desktop não estiver instalado, instalar automaticamente (winget ou instalador oficial)
  4. Verificar se o Docker está ativo; se não, iniciar e aguardar normalizar
  5. Registrar webhook na Evolution (se EVOLUTION_WEBHOOK_AUTO_REGISTER=true no .env)
  6. Rodar scheduler_pysql_evolution.py (e servidor webhook em thread)
.EXAMPLE
  PS> .\iniciar_pysql_evolution.ps1
#>

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

# 0) Garantir ambiente limpo: encerrar qualquer instancia anterior do fluxo PySQL+Evolution
$pararScript = Join-Path $ProjectRoot "parar_pysql_evolution.ps1"
if (Test-Path $pararScript) {
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host " Orquestrador PySQL + Evolution API" -ForegroundColor Cyan
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host "[0/7] Garantindo ambiente limpo (encerrando processos anteriores)..." -ForegroundColor Yellow
    & $pararScript | Out-Host
    if ($LASTEXITCODE -ne 0) {
        Write-Host "      Aviso: parar_pysql_evolution retornou $LASTEXITCODE. Continuando." -ForegroundColor Yellow
    } else {
        Write-Host "      OK." -ForegroundColor Green
    }
} else {
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host " Orquestrador PySQL + Evolution API" -ForegroundColor Cyan
    Write-Host "============================================================" -ForegroundColor Cyan
}

# 1) ExecutionPolicy (só CurrentUser, sem elevação)
try {
    $current = Get-ExecutionPolicy -Scope CurrentUser -ErrorAction SilentlyContinue
    if ($current -eq "Restricted" -or $current -eq "Undefined") {
        Write-Host "[1/7] Ajustando politica de execucao (RemoteSigned, CurrentUser)..." -ForegroundColor Yellow
        Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser -Force
        Write-Host "      OK." -ForegroundColor Green
    } else {
        Write-Host "[1/7] Politica de execucao ja permitida para este usuario." -ForegroundColor Green
    }
} catch {
    Write-Host "[1/7] Aviso: nao foi possivel alterar ExecutionPolicy. Continuando..." -ForegroundColor Yellow
}

# 2) Ativar venv
$venvActivate = Join-Path $ProjectRoot ".venv\Scripts\Activate.ps1"
if (-not (Test-Path $venvActivate)) {
    Write-Host "[2/7] ERRO: venv nao encontrada em .venv\Scripts\Activate.ps1" -ForegroundColor Red
    exit 1
}
Write-Host "[2/7] Ativando venv..." -ForegroundColor Yellow
. $venvActivate
Write-Host "      OK." -ForegroundColor Green

function Get-DockerDesktopExePath {
    $dockerPaths = @(
        "${Env:ProgramFiles}\Docker\Docker\Docker Desktop.exe",
        "${Env:ProgramFiles(x86)}\Docker\Docker\Docker Desktop.exe"
    )
    foreach ($p in $dockerPaths) {
        if (Test-Path $p) { return $p }
    }
    return $null
}

function Test-DockerDaemonReady {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { return $false }
    try {
        $null = docker info 2>&1
        return ($LASTEXITCODE -eq 0)
    } catch {
        return $false
    }
}

function Install-DockerDesktopIfNeeded {
    Write-Host "[3/7] Verificando instalacao do Docker Desktop..." -ForegroundColor Yellow
    if (Test-DockerDaemonReady) {
        Write-Host "      Docker ja esta ativo (daemon OK)." -ForegroundColor Green
        return $true
    }
    if (Get-DockerDesktopExePath) {
        Write-Host "      Docker Desktop ja instalado." -ForegroundColor Green
        return $true
    }

    Write-Host "      Nao encontrado. Tentando instalacao automatica..." -ForegroundColor Yellow
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if ($winget) {
        try {
            $proc = Start-Process -FilePath $winget.Source -ArgumentList @(
                "install", "-e", "--id", "Docker.DockerDesktop",
                "--accept-package-agreements", "--accept-source-agreements"
            ) -Wait -PassThru -NoNewWindow
            if ($proc.ExitCode -eq 0 -or $proc.ExitCode -eq $null) {
                Write-Host "      winget concluiu (codigo $($proc.ExitCode))." -ForegroundColor Green
            } else {
                Write-Host "      winget retornou codigo $($proc.ExitCode). Tentando instalador oficial..." -ForegroundColor Yellow
            }
        } catch {
            Write-Host "      winget falhou: $($_.Exception.Message). Tentando instalador oficial..." -ForegroundColor Yellow
        }
    } else {
        Write-Host "      winget nao disponivel. Usando instalador oficial..." -ForegroundColor Yellow
    }

    if ($winget -and -not (Get-DockerDesktopExePath)) {
        $t = 0
        while ($t -lt 90 -and -not (Get-DockerDesktopExePath)) {
            Start-Sleep -Seconds 5
            $t += 5
            Write-Host "      Aguardando arquivos do Docker Desktop (apos winget)... ${t}s" -ForegroundColor Gray
        }
    }

    if (-not (Get-DockerDesktopExePath)) {
        $installerUrl = "https://desktop.docker.com/win/stable/amd64/Docker%20Desktop%20Installer.exe"
        $installerPath = Join-Path $env:TEMP "DockerDesktopInstaller.exe"
        try {
            Write-Host "      Baixando instalador do Docker..." -ForegroundColor Yellow
            Invoke-WebRequest -Uri $installerUrl -OutFile $installerPath -UseBasicParsing
            Write-Host "      Executando instalador (UAC pode solicitar elevacao)..." -ForegroundColor Yellow
            $p = Start-Process -FilePath $installerPath -ArgumentList @("install", "--quiet", "--accept-license") -Wait -PassThru -Verb RunAs
            if ($p -and $p.ExitCode -ne 0) {
                Write-Host "      Aviso: instalador retornou codigo $($p.ExitCode)." -ForegroundColor Yellow
            }
        } catch {
            Write-Host "      ERRO: nao foi possivel instalar o Docker Desktop automaticamente: $($_.Exception.Message)" -ForegroundColor Red
            Write-Host "      Instale manualmente: https://docs.docker.com/desktop/install/windows-install/" -ForegroundColor Yellow
            return $false
        }
    }

    $deadline = (Get-Date).AddMinutes(5)
    while ((Get-Date) -lt $deadline) {
        if (Get-DockerDesktopExePath) {
            Write-Host "      Docker Desktop detectado apos instalacao." -ForegroundColor Green
            return $true
        }
        Start-Sleep -Seconds 5
        Write-Host "      Aguardando conclusao da instalacao do Docker Desktop..." -ForegroundColor Gray
    }
    if (-not (Get-DockerDesktopExePath)) {
        Write-Host "      Aviso: Docker Desktop ainda nao apareceu nos caminhos padrao. Reinicie o PC se a instalacao tiver pedido." -ForegroundColor Yellow
        return $false
    }
    return $true
}

# 3) Instalar Docker Desktop em maquina nova (se ausente)
$null = Install-DockerDesktopIfNeeded

# 4) Docker: verificar e, se desligado, iniciar e aguardar
Write-Host "[4/7] Verificando Docker..." -ForegroundColor Yellow
$dockerOk = $false
try {
    $null = docker info 2>&1
    if ($LASTEXITCODE -eq 0) { $dockerOk = $true }
} catch {}

if (-not $dockerOk) {
    $dockerExe = Get-DockerDesktopExePath
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

# 5) Registrar webhook na Evolution (se .env tiver EVOLUTION_WEBHOOK_AUTO_REGISTER=true)
Write-Host "[5/7] Verificando/registrando webhook na Evolution API..." -ForegroundColor Yellow
& (Join-Path $ProjectRoot ".venv\Scripts\python.exe") (Join-Path $ProjectRoot "evolution_api\registrar_webhook.py")
if ($LASTEXITCODE -ne 0) { Write-Host "      Aviso: registro do webhook falhou. Continuando." -ForegroundColor Yellow }
else { Write-Host "      OK." -ForegroundColor Green }

# 6) Rodar o scheduler (e webhook de comando por @ no WhatsApp, se habilitado)
Write-Host "[6/7] Iniciando scheduler PySQL + Evolution (e webhook)..." -ForegroundColor Yellow
Write-Host "============================================================" -ForegroundColor Cyan
& (Join-Path $ProjectRoot ".venv\Scripts\python.exe") (Join-Path $ProjectRoot "scheduler_pysql_evolution.py")
exit $LASTEXITCODE
