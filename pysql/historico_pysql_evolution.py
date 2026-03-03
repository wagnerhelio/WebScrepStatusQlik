"""
Histórico de envio e execução do fluxo PySQL + Evolution API.

Armazena em JSON (historico_pysql_evolution.json) para:
- Saber se já houve envio no dia (1x por dia)
- Calcular "tempo sem intercorrências" para o resumo no WhatsApp
"""

import json
import os
from datetime import datetime
from pathlib import Path

# Caminho do histórico (pysql/historico_pysql_evolution.json)
SCRIPT_DIR = Path(__file__).resolve().parent
ARQUIVO_HISTORICO = SCRIPT_DIR / "historico_pysql_evolution.json"
MAX_REGISTROS_ENVIO = 365


def _carregar():
    """Carrega o arquivo de histórico. Retorna estrutura padrão se não existir."""
    padrao = {"envios": [], "ultima_intercorrencia": None}
    if not ARQUIVO_HISTORICO.exists():
        return padrao
    try:
        with open(ARQUIVO_HISTORICO, "r", encoding="utf-8") as f:
            data = json.load(f)
        data.setdefault("envios", [])
        data.setdefault("ultima_intercorrencia", None)
        return data
    except Exception:
        return padrao


def _salvar(data: dict) -> None:
    """Salva o histórico no disco."""
    os.makedirs(SCRIPT_DIR, exist_ok=True)
    with open(ARQUIVO_HISTORICO, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def registrar_envio(sucesso: bool, timestamp: datetime | None = None) -> None:
    """
    Chamado pelo scheduler após rodar o fluxo.
    - sucesso=True: adiciona entrada em envios e limpa ultima_intercorrencia.
    - sucesso=False: atualiza ultima_intercorrencia (não adiciona envio).
    """
    agora = timestamp or datetime.now()
    data = _carregar()
    if sucesso:
        data["envios"].append({
            "data": agora.strftime("%Y-%m-%d"),
            "timestamp": agora.isoformat(),
            "sucesso": True,
        })
        # Mantém só os últimos N registros
        if len(data["envios"]) > MAX_REGISTROS_ENVIO:
            data["envios"] = data["envios"][-MAX_REGISTROS_ENVIO:]
        data["ultima_intercorrencia"] = None
    else:
        data["ultima_intercorrencia"] = agora.isoformat()
    _salvar(data)


def data_ultimo_envio_sucesso() -> str | None:
    """
    Retorna a data (YYYY-MM-DD) do último envio com sucesso, ou None.
    Usado pelo scheduler para saber se já enviou hoje.
    """
    data = _carregar()
    envios_ok = [e for e in data["envios"] if e.get("sucesso")]
    if not envios_ok:
        return None
    return envios_ok[-1].get("data")


def texto_tempo_sem_intercorrencias() -> str:
    """
    Lê o histórico e retorna texto para o resumo WhatsApp, ex.:
    "Tempo sem intercorrências: 5 dias" ou "Nenhuma falha registrada"
    """
    data = _carregar()
    ultima = data.get("ultima_intercorrencia")
    if not ultima:
        return "Tempo sem intercorrências: nenhuma falha registrada."
    try:
        dt = datetime.fromisoformat(ultima.replace("Z", "+00:00"))
        if dt.tzinfo:
            dt = dt.replace(tzinfo=None)
        dias = (datetime.now() - dt).days
        if dias == 0:
            return "Tempo sem intercorrências: desde hoje (após última falha)."
        if dias == 1:
            return "Tempo sem intercorrências: 1 dia."
        return f"Tempo sem intercorrências: {dias} dias."
    except Exception:
        return "Tempo sem intercorrências: nenhuma falha registrada."
