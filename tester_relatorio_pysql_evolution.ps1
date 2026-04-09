#Requires -Version 5.1
<#
.SYNOPSIS
  Teste de relatorios PySQL enviados apenas ao grupo de controle.
.DESCRIPTION
  Usa a venv e executa tester_relatorio_pysql_evolution.py (scripts pysql + envio com prefixo [TESTE]).
  Destino: EVO_GRUPO_CONTROLE ou EVO_GRUPO_ADMIN — nao envia ao grupo oficial.
.EXAMPLE
  PS> .\tester_relatorio_pysql_evolution.ps1
#>

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

$venvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $venvPython)) {
    Write-Host "ERRO: .venv nao encontrada. Execute iniciar_pysql_evolution.ps1 uma vez ou: python -m venv .venv" -ForegroundColor Red
    exit 1
}

& $venvPython (Join-Path $ProjectRoot "tester_relatorio_pysql_evolution.py")
exit $LASTEXITCODE
