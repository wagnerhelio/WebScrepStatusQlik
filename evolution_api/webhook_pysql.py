"""
Webhook Evolution API: comando por WhatsApp para disparar relatório PySQL.

Quando alguém marca o robô (@número do robô) no WhatsApp, o webhook pergunta:
  "Deseja que execute o relatório? 1 para sim, 2 para não"
- Resposta 1: executa send_pysql_evolution e envia o relatório também para quem pediu.
- Resposta 2: responde "Tudo bem, obrigado!" e volta a monitorar.

Requer:
  - Evolution API configurada para enviar evento MESSAGES_UPSERT para esta URL.
  - Variável EVOLUTION_BOT_NUMBER no .env (número do WhatsApp da instância, só dígitos).

Uso standalone:
  python evolution_api/webhook_pysql.py

Ou o webhook é iniciado em thread pelo scheduler_pysql_evolution.py (quando WEBHOOK_PYSQL_ENABLED=true).

Configurar webhook na Evolution API (uma vez):
  POST {{EVOLUTION_BASE_URL}}/webhook/set/{{EVOLUTION_INSTANCE_NAME}}
  Header: apikey: {{EVOLUTION_API_TOKEN}}
  Body (JSON): {"enabled": true, "url": "http://SEU_IP:5050/webhook", "events": ["MESSAGES_UPSERT"]}
  Se a Evolution não alcançar localhost, use ngrok ou o IP da máquina na rede.
"""

import os
import sys
import json
import re
import subprocess
import queue
from datetime import datetime
from pathlib import Path
from threading import Thread

# Fila de pedidos de relatório (preenchida pelo scheduler para executar no thread principal e exibir logs no console)
RELATORIO_PEDIDO_QUEUE = None

# Raiz do projeto
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Carrega .env
try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")
    load_dotenv(PROJECT_ROOT / "evolution_api" / ".env")
except Exception:
    pass

# Configurações
EVOLUTION_BOT_NUMBER = (os.getenv("EVOLUTION_BOT_NUMBER") or "").strip().replace(" ", "")
WEBHOOK_PYSQL_PORT = int(os.getenv("WEBHOOK_PYSQL_PORT", "5050"))
WEBHOOK_PYSQL_ENABLED = os.getenv("WEBHOOK_PYSQL_ENABLED", "true").strip().lower() in ("1", "true", "yes")
ARQUIVO_ESTADO = PROJECT_ROOT / "pysql" / "estado_webhook_pysql.json"
TIMEOUT_CONFIRMACAO_SEG = int(os.getenv("WEBHOOK_PYSQL_TIMEOUT_CONFIRMACAO", "300"))  # 5 min
WEBHOOK_DEBUG = os.getenv("WEBHOOK_DEBUG", "").strip().lower() in ("1", "true", "yes")

# Mensagens
MSG_CONFIRME = "Deseja que execute o relatório? 1 para sim, 2 para não"
MSG_OBRIGADO = "Tudo bem, obrigado!"
MSG_EXECUTANDO = "⏳ Executando o relatório PySQL. Você receberá os arquivos em breve."
MSG_ERRO = "❌ Erro ao executar o relatório. Tente novamente mais tarde ou verifique os logs."


def _carregar_estado():
    """Carrega estado de confirmação (quem está aguardando 1/2)."""
    if not ARQUIVO_ESTADO.exists():
        return {}
    try:
        with open(ARQUIVO_ESTADO, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _salvar_estado(estado):
    """Salva estado em JSON."""
    ARQUIVO_ESTADO.parent.mkdir(parents=True, exist_ok=True)
    with open(ARQUIVO_ESTADO, "w", encoding="utf-8") as f:
        json.dump(estado, f, indent=2, ensure_ascii=False)


def _limpar_expirados(estado):
    """Remove entradas com timestamp expirado."""
    agora_ts = datetime.now().timestamp()
    return {
        k: v for k, v in estado.items()
        if (agora_ts - v.get("timestamp", 0)) <= TIMEOUT_CONFIRMACAO_SEG
    }


def _extrair_texto(data):
    """Extrai texto da mensagem (conversation ou extendedTextMessage)."""
    msg = data.get("message") or data.get("msg") or {}
    if isinstance(msg, str):
        return msg.strip()
    if not isinstance(msg, dict):
        return ""
    texto = msg.get("conversation") or (msg.get("extendedTextMessage") or {}).get("text") or ""
    return (texto or "").strip()


def _extrair_mentioned_jids(data):
    """Extrai lista de JIDs mencionados (@) na mensagem (message.contextInfo ou data.contextInfo)."""
    msg = data.get("message") or data.get("msg") or {}
    ctx = data.get("contextInfo") or {}
    if isinstance(msg, dict):
        ext = msg.get("extendedTextMessage") or {}
        ctx = ctx or ext.get("contextInfo") or {}
    if not isinstance(ctx, dict):
        return []
    return ctx.get("mentionedJid") or []


def _bot_foi_mencionado(data):
    """Verifica se o número do robô foi mencionado ou se a mensagem é comando direto (DM)."""
    if not EVOLUTION_BOT_NUMBER:
        return False
    bot_jid = f"{EVOLUTION_BOT_NUMBER}@s.whatsapp.net"
    mentioned = _extrair_mentioned_jids(data)
    if bot_jid in mentioned:
        return True
    # DM: se remoteJid é o próprio bot (conversa 1:1 com o bot), qualquer mensagem pode ser comando
    key = data.get("key") or {}
    remote = (key.get("remoteJid") or "").lower()
    # Em DM o remoteJid é número@s.whatsapp.net; em grupo é xxx@g.us
    if remote.endswith("@s.whatsapp.net"):
        digits_remote = re.sub(r"\D", "", remote)
        digits_bot = re.sub(r"\D", "", EVOLUTION_BOT_NUMBER)
        if digits_remote == digits_bot:
            return True
    # Palavra-chave: "relatório" ou "relatorio" dispara sem precisar marcar @
    texto = _extrair_texto(data).lower()
    if "relatório" in texto or "relatorio" in texto:
        # No grupo: só escrever "relatório" (ou "relatorio") já aciona o bot
        if remote.endswith("@g.us"):
            return True
        # Em DM com o bot, "relatório" dispara a pergunta
        if remote.endswith("@s.whatsapp.net"):
            digits_remote = re.sub(r"\D", "", remote)
            if digits_remote == re.sub(r"\D", "", EVOLUTION_BOT_NUMBER):
                return True
    return False


def _enviar_resposta(remote_jid, texto, client, instance_id, instance_token):
    """Envia mensagem de texto via Evolution API."""
    try:
        from evolutionapi.client import EvolutionClient
        from evolutionapi.models.message import TextMessage
    except ImportError:
        return False
    try:
        client.messages.send_text(
            instance_id,
            TextMessage(number=remote_jid, text=texto),
            instance_token,
        )
        return True
    except Exception as e:
        print(f"[webhook] Erro ao enviar resposta: {e}", flush=True)
        return False


def _rodar_relatorio_e_enviar_para(remote_jid):
    """Executa send_pysql_evolution com --enviar-para e envia relatório também ao requester."""
    script = PROJECT_ROOT / "evolution_api" / "send_pysql_evolution.py"
    if not script.exists():
        return False, "Script não encontrado"
    env = {
        **os.environ,
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUTF8": "1",
        "PYTHONUNBUFFERED": "1",
    }
    print(f"[webhook] Iniciando execução do relatório PySQL (destino: {remote_jid})...", flush=True)
    sys.stdout.flush()
    sys.stderr.flush()
    try:
        result = subprocess.run(
            [sys.executable, "-u", str(script), "--enviar-para", remote_jid],
            cwd=PROJECT_ROOT,
            env=env,
            capture_output=False,
            timeout=10800,
            text=True,
            stdout=sys.stdout,
            stderr=sys.stderr,
        )
        if result.returncode == 0:
            print("[webhook] Relatório PySQL concluído com sucesso.", flush=True)
            return True, None
        print(f"[webhook] Relatório PySQL falhou (código {result.returncode}).", flush=True)
        return False, f"código {result.returncode}"
    except subprocess.TimeoutExpired:
        print("[webhook] Relatório PySQL: timeout na execução.", flush=True)
        return False, "Timeout na execução"
    except Exception as e:
        print(f"[webhook] Erro ao executar relatório: {e}", flush=True)
        return False, str(e)


def _processar_um_item(data, enviar_cb):
    """Processa um único item do payload (um objeto com key, message, etc.)."""
    key = data.get("key") or {}
    if key.get("fromMe") is True:
        return
    remote_jid = (key.get("remoteJid") or "").strip()
    if not remote_jid:
        return
    texto = _extrair_texto(data)
    if WEBHOOK_DEBUG:
        print(f"[webhook] msg remoteJid={remote_jid} texto={repr(texto)[:80]}", flush=True)
    estado = _carregar_estado()
    estado = _limpar_expirados(estado)
    aguardando = estado.get(remote_jid)

    # Já está aguardando confirmação (1 ou 2)
    if aguardando:
        opcao = texto.strip() if texto else ""
        if opcao == "1" or opcao.startswith("1"):
            del estado[remote_jid]
            _salvar_estado(estado)
            enviar_cb(remote_jid, MSG_EXECUTANDO)
            print(f"[webhook] Usuário respondeu 1 (executar relatório) para {remote_jid}.", flush=True)
            if RELATORIO_PEDIDO_QUEUE is not None:
                RELATORIO_PEDIDO_QUEUE.put(remote_jid)
                print("[webhook] Pedido enfileirado; o relatório será executado no thread principal (logs no console).", flush=True)
            else:
                ok, err = _rodar_relatorio_e_enviar_para(remote_jid)
                if not ok:
                    enviar_cb(remote_jid, MSG_ERRO + (f" ({err[:100]})" if err else ""))
            return
        if opcao == "2" or opcao.startswith("2"):
            del estado[remote_jid]
            _salvar_estado(estado)
            enviar_cb(remote_jid, MSG_OBRIGADO)
            return
        return

    # Nova menção ou palavra-chave: pergunta 1 ou 2
    if _bot_foi_mencionado(data):
        if WEBHOOK_DEBUG:
            print(f"[webhook] acionado para {remote_jid}, enviando pergunta 1/2", flush=True)
        estado[remote_jid] = {"estado": "aguardando_confirmacao", "timestamp": datetime.now().timestamp()}
        _salvar_estado(estado)
        enviar_cb(remote_jid, MSG_CONFIRME)


def processar_webhook(body, enviar_cb):
    """
    Processa o payload do webhook Evolution (MESSAGES_UPSERT).
    Aceita data como objeto ou como array (Evolution pode enviar lista de mensagens).
    """
    event = (body.get("event") or "").lower()
    if event not in ("messages.upsert", "messages_upsert"):
        if WEBHOOK_DEBUG and body.get("event"):
            print(f"[webhook] evento ignorado: {body.get('event')}", flush=True)
        return

    data = body.get("data") or body
    # Evolution pode enviar data como array de mensagens
    itens = data if isinstance(data, list) else [data]
    for item in itens:
        if isinstance(item, dict):
            _processar_um_item(item, enviar_cb)


def criar_app_flask():
    """Cria app Flask que recebe POST no webhook e usa Evolution para responder."""
    try:
        from flask import Flask, request, jsonify
    except ImportError as e:
        raise ImportError("Flask não instalado. Execute: pip install flask") from e

    # Importações que dependem do projeto (client Evolution)
    sys.path.insert(0, str(PROJECT_ROOT))
    from evolution_api.send_pysql_evolution import (
        client,
        evo_instance_id,
        evo_instance_token,
        enviar_mensagem_texto,
    )

    app = Flask(__name__)

    def enviar_cb(remote_jid, texto):
        return enviar_mensagem_texto(remote_jid, texto)

    @app.route("/webhook", methods=["POST", "GET"])
    @app.route("/webhook/messages-upsert", methods=["POST"])
    def webhook():
        if request.method == "GET":
            return jsonify({"status": "ok", "service": "webhook_pysql"}), 200
        try:
            body = request.get_json(force=True, silent=True) or {}
            event = body.get("event") or "(sem event)"
            print(f"[webhook] POST recebido event={event}", flush=True)
            processar_webhook(body, enviar_cb)
            return jsonify({"status": "ok"}), 200
        except Exception as e:
            print(f"[webhook] Erro: {e}", flush=True)
            return jsonify({"status": "error", "message": str(e)}), 500

    return app


def run_webhook_server():
    """Inicia o servidor Flask do webhook."""
    if not EVOLUTION_BOT_NUMBER:
        print("[webhook] EVOLUTION_BOT_NUMBER não definido no .env - respostas a @ desativadas.", flush=True)
    app = criar_app_flask()
    host = os.getenv("WEBHOOK_PYSQL_HOST", "0.0.0.0")
    print(f"[webhook] PySQL ouvindo em http://{host}:{WEBHOOK_PYSQL_PORT}/webhook", flush=True)
    app.run(host=host, port=WEBHOOK_PYSQL_PORT, threaded=True, use_reloader=False)


if __name__ == "__main__":
    run_webhook_server()
