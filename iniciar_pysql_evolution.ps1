#Requires -Version 5.1
<#
.SYNOPSIS
  Orquestrador: ativa venv, garante política de execução, verifica/inicia Docker e roda o scheduler PySQL + Evolution.
.DESCRIPTION
  Execute este script em vez de "python scheduler_pysql_evolution.py" para:
  1. Ajustar ExecutionPolicy (RemoteSigned, CurrentUser) se necessário
  2. Verificar Python (3.10+), criar .venv e instalar dependências se necessário; ativar a venv
  3. Se o Docker Desktop não estiver instalado, instalar automaticamente (winget ou instalador oficial)
  4. Verificar se o Docker está ativo; se não, iniciar e aguardar normalizar
  5. Opcional: subir stack Evolution API no Docker (docker compose) se EVOLUTION_DOCKER_COMPOSE_UP=true
  6. Registrar webhook na Evolution (se EVOLUTION_WEBHOOK_AUTO_REGISTER=true no .env)
  7. Rodar scheduler_pysql_evolution.py (e servidor webhook em thread)
.EXAMPLE
  PS> .\iniciar_pysql_evolution.ps1
#>

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

function Import-DotEnvForProcess {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) { return }
    Get-Content -LiteralPath $Path -Encoding UTF8 | ForEach-Object {
        $line = $_ -replace "`r$", ""
        $t = $line.Trim()
        if ($t -eq "" -or $t.StartsWith("#")) { return }
        $ix = $t.IndexOf("=")
        if ($ix -lt 1) { return }
        $key = $t.Substring(0, $ix).Trim()
        $val = $t.Substring($ix + 1).Trim()
        if ($val.Length -ge 2) {
            $q0 = $val[0]
            $q1 = $val[$val.Length - 1]
            if (($q0 -eq [char]34 -and $q1 -eq [char]34) -or ($q0 -eq [char]39 -and $q1 -eq [char]39)) {
                $val = $val.Substring(1, $val.Length - 2)
            }
        }
        [Environment]::SetEnvironmentVariable($key, $val, "Process")
    }
}
Import-DotEnvForProcess (Join-Path $ProjectRoot ".env")

# 0) Garantir ambiente limpo: encerrar qualquer instancia anterior do fluxo PySQL+Evolution
$pararScript = Join-Path $ProjectRoot "parar_pysql_evolution.ps1"
if (Test-Path $pararScript) {
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host " Orquestrador PySQL + Evolution API" -ForegroundColor Cyan
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host "[0/8] Garantindo ambiente limpo (encerrando processos anteriores)..." -ForegroundColor Yellow
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
        Write-Host "[1/8] Ajustando politica de execucao (RemoteSigned, CurrentUser)..." -ForegroundColor Yellow
        Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser -Force
        Write-Host "      OK." -ForegroundColor Green
    } else {
        Write-Host "[1/8] Politica de execucao ja permitida para este usuario." -ForegroundColor Green
    }
} catch {
    Write-Host "[1/8] Aviso: nao foi possivel alterar ExecutionPolicy. Continuando..." -ForegroundColor Yellow
}

# 2) Python: versao minima, criar .venv se ausente, pip install, ativar venv
$MinPythonMajor = 3
$MinPythonMinor = 10

function Get-PythonVersionLine {
    param(
        [Parameter(Mandatory)][string]$CommandName,
        [string[]]$PrefixArgs = @()
    )
    try {
        if ($PrefixArgs.Count -gt 0) {
            $o = & $CommandName @PrefixArgs "--version" 2>&1
        } else {
            $o = & $CommandName --version 2>&1
        }
        return ($o | Out-String).Trim()
    } catch {
        return $null
    }
}

function Test-PythonVersionOk {
    param([string]$VersionLine, [int]$NeedMajor, [int]$NeedMinor)
    if ([string]::IsNullOrWhiteSpace($VersionLine)) { return $false }
    if ($VersionLine -match 'Python\s+(\d+)\.(\d+)') {
        $maj = [int]$Matches[1]
        $min = [int]$Matches[2]
        if ($maj -gt $NeedMajor) { return $true }
        if ($maj -eq $NeedMajor -and $min -ge $NeedMinor) { return $true }
    }
    return $false
}

function Resolve-PythonForVenv {
    param([int]$NeedMajor, [int]$NeedMinor)
    if (Get-Command py -ErrorAction SilentlyContinue) {
        $line = Get-PythonVersionLine "py" @("-3")
        if (Test-PythonVersionOk $line $NeedMajor $NeedMinor) {
            return @{ Mode = "py"; Args = @("-3"); VersionLine = $line }
        }
    }
    foreach ($name in @("python", "python3")) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if (-not $cmd) { continue }
        $line = Get-PythonVersionLine $name @()
        if (Test-PythonVersionOk $line $NeedMajor $NeedMinor) {
            return @{ Mode = "exe"; Exe = $cmd.Source; VersionLine = $line }
        }
    }
    return $null
}

Write-Host "[2/8] Verificando Python e ambiente virtual (.venv)..." -ForegroundColor Yellow
$pythonLauncher = Resolve-PythonForVenv $MinPythonMajor $MinPythonMinor
if (-not $pythonLauncher) {
    Write-Host "      ERRO: nenhum Python $($MinPythonMajor).$($MinPythonMinor)+ encontrado (py -3, python ou python3 no PATH)." -ForegroundColor Red
    Write-Host "      Instale Python $($MinPythonMajor).$($MinPythonMinor)+ em https://www.python.org/downloads/ ou 'winget install Python.Python.3.12'" -ForegroundColor Yellow
    exit 1
}
Write-Host "      Python OK: $($pythonLauncher.VersionLine)" -ForegroundColor Green

$venvDir = Join-Path $ProjectRoot ".venv"
$venvActivate = Join-Path $ProjectRoot ".venv\Scripts\Activate.ps1"
$venvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$reqFile = Join-Path $ProjectRoot "requirements.txt"

if (-not (Test-Path $venvActivate)) {
    Write-Host "      .venv nao encontrado. Criando em '$venvDir'..." -ForegroundColor Yellow
    if ($pythonLauncher.Mode -eq "py") {
        & py @($pythonLauncher.Args) -m venv $venvDir
    } else {
        & $pythonLauncher.Exe -m venv $venvDir
    }
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $venvPython)) {
        Write-Host "      ERRO: falha ao executar 'python -m venv .venv'." -ForegroundColor Red
        exit 1
    }
    if (-not (Test-Path $reqFile)) {
        Write-Host "      Aviso: requirements.txt nao encontrado. Pulei pip install." -ForegroundColor Yellow
    } else {
        Write-Host "      Instalando dependencias (requirements.txt). Pode levar alguns minutos..." -ForegroundColor Yellow
        & $venvPython -m pip install --upgrade pip
        if ($LASTEXITCODE -ne 0) {
            Write-Host "      ERRO: pip upgrade falhou." -ForegroundColor Red
            exit 1
        }
        & $venvPython -m pip install -r $reqFile
        if ($LASTEXITCODE -ne 0) {
            Write-Host "      ERRO: pip install -r requirements.txt falhou." -ForegroundColor Red
            exit 1
        }
        Write-Host "      Dependencias instaladas." -ForegroundColor Green
    }
} else {
    Write-Host "      .venv ja existe." -ForegroundColor Green
}

Write-Host "      Ativando venv..." -ForegroundColor Yellow
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
    Write-Host "[3/8] Verificando instalacao do Docker Desktop..." -ForegroundColor Yellow
    if (Test-DockerDaemonReady) {
        Write-Host "      Docker ja esta ativo (daemon OK)." -ForegroundColor Green
        Write-Host "      Nota: isso so confirma o motor Docker (docker info). Nao inicia containers da Evolution aqui." -ForegroundColor DarkGray
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
Write-Host "[4/8] Verificando Docker..." -ForegroundColor Yellow
$dockerOk = $false
try {
    $null = docker info 2>&1
    if ($LASTEXITCODE -eq 0) { $dockerOk = $true }
} catch {}

if (-not $dockerOk) {
    $dockerExe = Get-DockerDesktopExePath
    if ($dockerExe) {
        Write-Host "      Docker nao estava em execucao. Iniciando Docker Desktop..." -ForegroundColor Yellow
        Start-Process -FilePath $dockerExe -WindowStyle Minimized
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
Write-Host "      Lembrete: o app Docker Desktop so lista imagens/containers que voce sobe (ex.: passo [5/8] ou manualmente)." -ForegroundColor DarkGray

# 5) Opcional: stack Evolution API (API + Redis + Postgres) - so aparece no app apos compose up
Write-Host "[5/8] Evolution API no Docker (compose - opcional)..." -ForegroundColor Yellow
$composeUp = [Environment]::GetEnvironmentVariable("EVOLUTION_DOCKER_COMPOSE_UP", "Process")
$evoApiDir = Join-Path $ProjectRoot "evolution_api"
$composeFile = Join-Path $evoApiDir "docker-compose.yaml"
$evoEnvFile = Join-Path $evoApiDir ".env"

if ($composeUp -eq "true" -or $composeUp -eq "1") {
    if (-not (Test-Path -LiteralPath $composeFile)) {
        Write-Host "      Aviso: evolution_api\docker-compose.yaml nao encontrado." -ForegroundColor Yellow
    } elseif (-not (Test-Path -LiteralPath $evoEnvFile)) {
        Write-Host "      Aviso: crie evolution_api\.env (baseado em evolution_api\.env.example) para o compose." -ForegroundColor Yellow
    } elseif (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        Write-Host "      Aviso: comando 'docker' indisponivel." -ForegroundColor Yellow
    } else {
        Push-Location $evoApiDir
        try {
            Write-Host "      docker compose up -d (pasta evolution_api)..." -ForegroundColor Gray
            & docker compose up -d 2>&1 | Out-Host
            $exitCompose = $LASTEXITCODE
            if ($exitCompose -ne 0 -and (Get-Command docker-compose -ErrorAction SilentlyContinue)) {
                Write-Host "      Tentando docker-compose up -d..." -ForegroundColor Gray
                & docker-compose up -d 2>&1 | Out-Host
                $exitCompose = $LASTEXITCODE
            }
            if ($exitCompose -ne 0) {
                Write-Host "      Aviso: compose retornou $exitCompose. Confira evolution_api\.env, portas e logs." -ForegroundColor Yellow
            } else {
                Write-Host "      OK. Containers no Docker Desktop: evolution_api, evolution_redis, evolution_postgres (nomes do compose)." -ForegroundColor Green
            }
        } finally {
            Pop-Location
        }
    }
} else {
    Write-Host "      Pulado. Para subir API+Redis+Postgres localmente: EVOLUTION_DOCKER_COMPOSE_UP=true no .env da raiz." -ForegroundColor Gray
}

# 6) Registrar webhook na Evolution (se .env tiver EVOLUTION_WEBHOOK_AUTO_REGISTER=true)
Write-Host "[6/8] Verificando/registrando webhook na Evolution API..." -ForegroundColor Yellow
& (Join-Path $ProjectRoot ".venv\Scripts\python.exe") (Join-Path $ProjectRoot "evolution_api\registrar_webhook.py")
if ($LASTEXITCODE -ne 0) { Write-Host "      Aviso: registro do webhook falhou. Continuando." -ForegroundColor Yellow }
else { Write-Host "      OK." -ForegroundColor Green }

# 7) Rodar o scheduler (e webhook de comando por @ no WhatsApp, se habilitado)
Write-Host "[7/8] Iniciando scheduler PySQL + Evolution (e webhook)..." -ForegroundColor Yellow
Write-Host "============================================================" -ForegroundColor Cyan
& (Join-Path $ProjectRoot ".venv\Scripts\python.exe") (Join-Path $ProjectRoot "scheduler_pysql_evolution.py")
exit $LASTEXITCODE
