#Requires -Version 5.1
<#
.SYNOPSIS
  Envia mensagem de teste ao grupo de controle (WhatsApp via Evolution).
.DESCRIPTION
  Usa a venv do projeto e executa testar_pysql_evolution.py (OK + hostname/IPs).
  Destino: EVO_GRUPO_CONTROLE ou EVO_GRUPO_ADMIN — nao envia ao grupo oficial.
.EXAMPLE
  PS> .\testar_pysql_evolution.ps1
#>

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

$venvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $venvPython)) {
    Write-Host "ERRO: .venv nao encontrada. Execute iniciar_pysql_evolution.ps1 uma vez ou: python -m venv .venv" -ForegroundColor Red
    exit 1
}

& $venvPython (Join-Path $ProjectRoot "testar_pysql_evolution.py")
exit $LASTEXITCODE
