#!/usr/bin/env python3
"""
Script de teste: lista todos os grupos da instância e envia "Teste de Conexão" para cada um.

Uso (com a venv do projeto):
  .venv\\Scripts\\python.exe evolution_api/send_test_listar_grupos.py
  ou, com venv ativada: python evolution_api/send_test_listar_grupos.py

Variáveis de ambiente (.env em evolution_api ou raiz):
  EVOLUTION_BASE_URL     - URL da API (default: http://localhost:8080)
  EVOLUTION_API_TOKEN   - ou AUTHENTICATION_API_KEY (apikey da Evolution API)
  EVOLUTION_INSTANCE_ID - nome da instância (ex.: bisspgo, odisseu)
"""

import os
import sys
import time
import requests
from dotenv import load_dotenv

# Configuração UTF-8 para Windows
if os.name == 'nt':
    try:
        os.system('chcp 65001 > nul')
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Carrega .env do diretório do script ou do cwd
script_dir = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(script_dir, ".env"))
load_dotenv()

evo_base_url = os.getenv("EVOLUTION_BASE_URL", "http://localhost:8080")
evo_api_token = os.getenv("EVOLUTION_API_TOKEN") or os.getenv("AUTHENTICATION_API_KEY")
evo_instance_id = os.getenv("EVOLUTION_INSTANCE_ID", "odisseu")

MENSAGEM_TESTE = "Teste de Conexão"
DELAY_ENTRE_GRUPOS_SEG = 2  # evita flood


def buscar_grupos():
    """Busca todos os grupos da instância via Evolution API."""
    url = f"{evo_base_url}/group/fetchAllGroups/{evo_instance_id}?getParticipants=false"
    headers = {"apikey": evo_api_token, "Content-Type": "application/json"}
    try:
        r = requests.get(url, headers=headers, timeout=30)
        if r.status_code == 200:
            return r.json()
        print(f"❌ API grupos: {r.status_code} - {r.text[:200]}")
        return None
    except Exception as e:
        print(f"❌ Erro ao buscar grupos: {e}")
        return None


def enviar_texto(grupo_jid: str, texto: str) -> bool:
    """Envia mensagem de texto para um grupo (JID)."""
    url = f"{evo_base_url}/message/sendText/{evo_instance_id}"
    headers = {"apikey": evo_api_token, "Content-Type": "application/json"}
    # Evolution API v2: number = JID do grupo, text = conteúdo
    body = {"number": grupo_jid, "text": texto}
    try:
        r = requests.post(url, headers=headers, json=body, timeout=30)
        if r.status_code in (200, 201):
            return True
        print(f"   Resposta: {r.status_code} - {r.text[:150]}")
        return False
    except Exception as e:
        print(f"   Erro: {e}")
        return False


def main():
    print("=" * 70)
    print("📤 TESTE: Listar grupos e enviar 'Teste de Conexão' para cada um")
    print("=" * 70)
    print(f"🌐 URL: {evo_base_url}")
    print(f"📱 Instância: {evo_instance_id}")
    print(f"💬 Mensagem: {MENSAGEM_TESTE!r}")
    print()

    if not evo_api_token:
        print("❌ Defina EVOLUTION_API_TOKEN ou AUTHENTICATION_API_KEY no .env")
        return 1

    grupos = buscar_grupos()
    if not grupos:
        print("❌ Nenhum grupo obtido. Verifique se a instância existe e está conectada.")
        return 1

    print(f"✅ Grupos encontrados: {len(grupos)}\n")

    ok = 0
    falha = 0
    for i, g in enumerate(grupos, 1):
        jid = g.get("id") or g.get("jid")
        nome = g.get("subject", "N/A")
        if not jid:
            continue
        if not jid.endswith("@g.us"):
            jid = f"{jid}@g.us"
        print(f"[{i}/{len(grupos)}] 📛 {nome}")
        print(f"         JID: {jid}")
        if enviar_texto(jid, MENSAGEM_TESTE):
            print(f"         ✅ Enviado")
            ok += 1
        else:
            print(f"         ❌ Falha no envio")
            falha += 1
        if i < len(grupos):
            time.sleep(DELAY_ENTRE_GRUPOS_SEG)

    print()
    print("=" * 70)
    print("📊 RESUMO")
    print("=" * 70)
    print(f"   Total de grupos: {len(grupos)}")
    print(f"   Enviados com sucesso: {ok}")
    print(f"   Falhas: {falha}")
    return 0 if falha == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
