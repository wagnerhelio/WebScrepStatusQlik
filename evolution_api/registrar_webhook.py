#!/usr/bin/env python3
"""
Registra o webhook PySQL na Evolution API (se EVOLUTION_WEBHOOK_AUTO_REGISTER=true).

Verifica GET /webhook/find/{instance}. Se a URL já estiver configurada e habilitada, não faz nada.
Caso contrário, envia POST /webhook/set/{instance} com o body no formato que a Evolution v2 exige.

Variáveis no .env (raiz do projeto):
  EVOLUTION_WEBHOOK_AUTO_REGISTER  - true para registrar/verificar na inicialização
  EVOLUTION_WEBHOOK_PUBLIC_URL     - URL que a Evolution deve chamar (ex.: http://10.242.31.154:5050/webhook)
  EVOLUTION_BASE_URL               - base da Evolution API (ex.: http://10.242.31.154:8080)
  EVOLUTION_API_TOKEN              - apikey
  EVOLUTION_INSTANCE_NAME          - nome da instância (ex.: bisspgo)

Uso: chamado automaticamente pelo iniciar_pysql_evolution.ps1 antes do scheduler.
      Ou manualmente: python evolution_api/registrar_webhook.py
"""

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")
    load_dotenv(PROJECT_ROOT / "evolution_api" / ".env")
except Exception:
    pass

try:
    import requests
except ImportError:
    requests = None


def main():
    auto = (os.getenv("EVOLUTION_WEBHOOK_AUTO_REGISTER") or "").strip().lower() in ("1", "true", "yes")
    if not auto:
        return 0

    url_public = (os.getenv("EVOLUTION_WEBHOOK_PUBLIC_URL") or "").strip().rstrip("/")
    base = (os.getenv("EVOLUTION_BASE_URL") or "").strip().rstrip("/")
    token = (os.getenv("EVOLUTION_API_TOKEN") or "").strip()
    instance = (os.getenv("EVOLUTION_INSTANCE_NAME") or "").strip()

    if not url_public:
        print("[webhook] EVOLUTION_WEBHOOK_PUBLIC_URL nao definido. Defina no .env (ex.: http://SEU_IP:5050/webhook)", flush=True)
        return 0
    if not all([base, token, instance]):
        print("[webhook] Faltam EVOLUTION_BASE_URL, EVOLUTION_API_TOKEN ou EVOLUTION_INSTANCE_NAME no .env", flush=True)
        return 0

    if not requests:
        print("[webhook] requests nao instalado. pip install requests (ou use o orquestrador)", flush=True)
        return 0

    headers = {"apikey": token, "Content-Type": "application/json"}
    find_url = f"{base}/webhook/find/{instance}"
    set_url = f"{base}/webhook/set/{instance}"

    # Normaliza para comparar (sem barra final)
    url_public_norm = url_public if url_public.endswith("/webhook") else url_public + "/webhook"

    try:
        r = requests.get(find_url, headers={"apikey": token}, timeout=10)
        if r.status_code == 200:
            data = r.json()
            # Resposta pode ser direta { enabled, url, events } ou dentro de .webhook
            w = data.get("webhook") if isinstance(data.get("webhook"), dict) else data
            if isinstance(w, dict):
                current_url = (w.get("url") or "").strip().rstrip("/")
                current_enabled = w.get("enabled") is True
                if current_url and current_url.rstrip("/") == url_public_norm.rstrip("/") and current_enabled:
                    print("[webhook] Webhook ja configurado na Evolution.", flush=True)
                    return 0
        # 404 ou URL diferente: registrar
    except Exception:
        pass  # segue para registrar

    body = {
        "webhook": {
            "enabled": True,
            "url": url_public_norm,
            "events": ["MESSAGES_UPSERT"],
            "webhookByEvents": False,
            "webhookBase64": False,
        }
    }
    try:
        r = requests.post(set_url, headers=headers, json=body, timeout=10)
        if r.status_code in (200, 201):
            print("[webhook] Webhook registrado na Evolution com sucesso.", flush=True)
            return 0
        print(f"[webhook] Evolution retornou {r.status_code}: {r.text[:200]}", flush=True)
        return 0  # nao falha o inicio do scheduler
    except Exception as e:
        print(f"[webhook] Erro ao registrar webhook: {e}", flush=True)
        return 0


if __name__ == "__main__":
    sys.exit(main())
