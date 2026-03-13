#Requires -Version 5.1
<#
.SYNOPSIS
  Encerra todos os processos do fluxo PySQL + Evolution (scheduler, webhook, send_pysql) para começar sempre limpo.
.DESCRIPTION
  Mata processos Python que estejam rodando scheduler_pysql_evolution.py, webhook Flask (porta 5050)
  ou send_pysql_evolution.py, evitando execuções encavaladas.
  Pode ser executado manualmente ou é chamado automaticamente pelo iniciar_pysql_evolution.ps1.
.EXAMPLE
  PS> .\parar_pysql_evolution.ps1
#>

$ErrorActionPreference = "Continue"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$WebhookPort = 5050

function Get-ProcessCommandLine {
    param([int]$ProcessId)
    try {
        $p = Get-CimInstance Win32_Process -Filter "ProcessId = $ProcessId" -ErrorAction SilentlyContinue
        if ($p) { return $p.CommandLine }
    } catch {}
    return $null
}

function Stop-PySQLEvolutionProcesses {
    $killed = @()
    $script:anyKilled = $false

    # 1) Processos que escutam na porta do webhook (5050)
    try {
        $conns = Get-NetTCPConnection -LocalPort $WebhookPort -State Listen -ErrorAction SilentlyContinue
        foreach ($c in $conns) {
            $pid = $c.OwningProcess
            if ($pid -and (Get-Process -Id $pid -ErrorAction SilentlyContinue)) {
                Write-Host "   Encerrando processo na porta $WebhookPort (PID $pid)..." -ForegroundColor Yellow
                Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
                $killed += $pid
                $script:anyKilled = $true
            }
        }
    } catch {
        # Get-NetTCPConnection pode falhar em alguns contextos
    }

    # 2) Processos Python cujo comando contém os scripts do fluxo PySQL + Evolution
    $patterns = @(
        "scheduler_pysql_evolution",
        "webhook_pysql",
        "send_pysql_evolution"
    )
    $pythonProcesses = Get-Process -Name python, pythonw -ErrorAction SilentlyContinue
    foreach ($proc in $pythonProcesses) {
        $cmd = Get-ProcessCommandLine -ProcessId $proc.Id
        if (-not $cmd) { continue }
        $match = $false
        $matchedPat = $null
        foreach ($pat in $patterns) {
            if ($cmd -match [regex]::Escape($pat)) { $match = $true; $matchedPat = $pat; break }
        }
        if ($match) {
            Write-Host "   Encerrando Python (PID $($proc.Id)): $matchedPat..." -ForegroundColor Yellow
            Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
            $killed += $proc.Id
            $script:anyKilled = $true
        }
    }

    if ($killed.Count -gt 0) {
        Start-Sleep -Seconds 2
    }
    return $killed
}

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " Parar PySQL + Evolution (limpar processos)" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

$script:anyKilled = $false
$killed = @(Stop-PySQLEvolutionProcesses)

if ($killed.Count -gt 0) {
    Write-Host "   Encerrados $($killed.Count) processo(s). Aguardando 2s..." -ForegroundColor Green
    Start-Sleep -Seconds 2
} else {
    Write-Host "   Nenhum processo do fluxo PySQL+Evolution em execucao." -ForegroundColor Gray
}

# Verificar se a porta 5050 ficou livre
$portInUse = $false
try {
    $c = Get-NetTCPConnection -LocalPort $WebhookPort -State Listen -ErrorAction SilentlyContinue
    if ($c) { $portInUse = $true }
} catch {}

if ($portInUse) {
    Write-Host "   Aviso: porta $WebhookPort ainda em uso. Tentando encerrar novamente..." -ForegroundColor Yellow
    $killed2 = @(Stop-PySQLEvolutionProcesses)
    Start-Sleep -Seconds 2
    $c2 = Get-NetTCPConnection -LocalPort $WebhookPort -State Listen -ErrorAction SilentlyContinue
    if ($c2) {
        Write-Host "   ERRO: porta $WebhookPort continua em uso. Encerre manualmente se necessario." -ForegroundColor Red
        exit 1
    }
}
Write-Host "   OK. Ambiente limpo para iniciar." -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
exit 0
