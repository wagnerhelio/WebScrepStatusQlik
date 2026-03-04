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


def _formatar_data_br(data_str: str) -> str:
    """Converte YYYY-MM-DD para DD/MM/YYYY."""
    try:
        parts = data_str.split("-")
        if len(parts) == 3:
            return f"{parts[2]}/{parts[1]}/{parts[0]}"
    except Exception:
        pass
    return data_str


def texto_tempo_sem_intercorrencias() -> str:
    """
    Lê o histórico e retorna texto para o resumo WhatsApp:
    - Sem falhas: "N dias consecutivos sem erros ou falhas"
    - Com falha: "Do dia X até o dia da falha: K dias... 1 falha no dia D. Depois M dias consecutivos..."
    """
    data = _carregar()
    envios = [e for e in data.get("envios", []) if e.get("sucesso")]
    ultima = data.get("ultima_intercorrencia")

    if not ultima:
        # Nenhuma falha: contabiliza dias consecutivos de envios com sucesso
        n = len(envios)
        if n == 0:
            return "Histórico: ainda sem envios registrados."
        if n == 1:
            return "1 dia consecutivo sem erros ou falhas."
        return f"{n} dias consecutivos sem erros ou falhas."

    try:
        dt = datetime.fromisoformat(ultima.replace("Z", "+00:00"))
        if dt.tzinfo:
            dt = dt.replace(tzinfo=None)
        data_falha = dt.strftime("%Y-%m-%d")
        data_falha_br = _formatar_data_br(data_falha)
    except Exception:
        return "Histórico: falha ao ler data da última intercorrência."

    # Envios antes da falha (data < data_falha)
    envios_antes = [e for e in envios if e.get("data", "") < data_falha]
    # Envios depois da falha (data > data_falha)
    envios_depois = [e for e in envios if e.get("data", "") > data_falha]

    k = len(envios_antes)
    m = len(envios_depois)

    if k > 0:
        primeira_data = min(e["data"] for e in envios_antes)
        primeira_br = _formatar_data_br(primeira_data)
        parte1 = f"Do dia {primeira_br} até o dia da falha: {k} dias sem erros ou falhas."
    else:
        parte1 = "Nenhum envio antes da falha."

    parte2 = f"1 falha registrada no dia {data_falha_br}."

    if m == 0:
        parte3 = "Ainda sem envios após a falha."
    elif m == 1:
        parte3 = "Depois 1 dia consecutivo sem erros ou falhas."
    else:
        parte3 = f"Depois {m} dias consecutivos sem erros ou falhas."

    return f"{parte1} {parte2} {parte3}"
