#!/usr/bin/env python3
"""
Script para listar todos os grupos de uma instância Evolution API com JID e nome.

Uso (com a venv do projeto, a partir da raiz do repositório):
  .venv\\Scripts\\python.exe evolution_api/tests/listar_grupos_odisseu.py
  ou, com venv ativada: python evolution_api/tests/listar_grupos_odisseu.py

Variáveis de ambiente (.env em evolution_api ou raiz):
  EVOLUTION_BASE_URL     - URL da API (default: http://localhost:8080)
  EVOLUTION_API_TOKEN   - ou AUTHENTICATION_API_KEY (apikey da Evolution API)
  EVOLUTION_INSTANCE_ID - nome da instância (default: odisseu)
"""

import os
import sys
import requests
import json
from dotenv import load_dotenv

# Configuração UTF-8 para Windows
if os.name == 'nt':
    try:
        os.system('chcp 65001 > nul')
        sys.stdout.reconfigure(encoding='utf-8')
    except:
        pass

# Carrega .env: pasta tests, depois evolution_api, depois cwd
script_dir = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(script_dir, ".env"))
load_dotenv(os.path.join(script_dir, "..", ".env"))
load_dotenv()

# Configurações da Evolution API
evo_base_url = os.getenv("EVOLUTION_BASE_URL", "http://localhost:8080")
evo_api_token = os.getenv("EVOLUTION_API_TOKEN") or os.getenv("AUTHENTICATION_API_KEY")
evo_instance_id = os.getenv("EVOLUTION_INSTANCE_ID", "odisseu")

def listar_grupos_completos():
    """Lista todos os grupos com informações completas."""
    print(f"🔍 LISTANDO GRUPOS DA INSTÂNCIA '{evo_instance_id.upper()}'")
    print("=" * 70)
    
    url = f"{evo_base_url}/group/fetchAllGroups/{evo_instance_id}?getParticipants=true"
    headers = {
        "apikey": evo_api_token,
        "Content-Type": "application/json"
    }
    
    print(f"🌐 URL: {url}")
    print(f"🔑 API Token: {(evo_api_token or '')[:10]}...")
    print(f"📱 Instância: {evo_instance_id}")
    
    try:
        print("\n📡 Fazendo requisição para a API...")
        response = requests.get(url, headers=headers, timeout=30)
        
        print(f"📊 Status HTTP: {response.status_code}")
        
        if response.status_code == 200:
            grupos = response.json()
            print(f"✅ SUCESSO! Total de grupos encontrados: {len(grupos)}")
            
            if len(grupos) == 0:
                print(f"⚠️ Nenhum grupo encontrado na instância {evo_instance_id}")
                return
            
            print("\n" + "=" * 70)
            print("👥 LISTA COMPLETA DE GRUPOS")
            print("=" * 70)
            
            for i, grupo in enumerate(grupos, 1):
                jid = grupo.get('id', 'N/A')
                nome = grupo.get('subject', 'N/A')
                tamanho = grupo.get('size', 0)
                criacao = grupo.get('creation', 0)
                dono = grupo.get('owner', 'N/A')
                participantes = grupo.get('participants', [])
                
                print(f"\n📋 GRUPO {i}:")
                print(f"   🆔 JID: {jid}")
                print(f"   📛 Nome: {nome}")
                print(f"   👥 Tamanho: {tamanho} participantes")
                print(f"   👑 Dono: {dono}")
                print(f"   📅 Criação: {criacao}")
                
                if participantes:
                    print(f"   👥 Participantes ({len(participantes)}):")
                    for participante in participantes:
                        pid = participante.get('id', 'N/A')
                        admin = participante.get('admin', 'N/A')
                        print(f"      - {pid} ({admin})")
                else:
                    print(f"   👥 Participantes: Nenhum listado")
                
                print(f"   {'-' * 50}")
            
            # Resumo final
            print(f"\n📊 RESUMO FINAL:")
            print(f"   Total de grupos: {len(grupos)}")
            
            # Lista apenas JID e nome para cópia fácil
            print(f"\n📋 LISTA SIMPLES (JID | NOME):")
            print("=" * 70)
            for grupo in grupos:
                jid = grupo.get('id', 'N/A')
                nome = grupo.get('subject', 'N/A')
                print(f"{jid} | {nome}")
            
            return grupos
            
        else:
            print(f"❌ ERRO: {response.status_code}")
            print(f"📄 Resposta: {response.text}")
            if response.status_code == 404 and "instance does not exist" in response.text:
                print(f"\n💡 Dica: A instância '{evo_instance_id}' não existe.")
                print(f"   Defina no .env: EVOLUTION_INSTANCE_ID=nome_da_sua_instancia")
                print(f"   (ex.: EVOLUTION_INSTANCE_ID=bisspgo)")
            return None
            
    except Exception as e:
        print(f"❌ Erro na requisição: {e}")
        import traceback
        print(f"🔍 Traceback: {traceback.format_exc()}")
        return None

def salvar_grupos_arquivo(grupos):
    """Salva a lista de grupos em arquivo JSON na pasta tests."""
    if not grupos:
        return
    
    try:
        arquivo = os.path.join(script_dir, "grupos_odisseu.json")
        with open(arquivo, 'w', encoding='utf-8') as f:
            json.dump(grupos, f, indent=2, ensure_ascii=False)
        print(f"\n💾 Lista de grupos salva em: {arquivo}")
    except Exception as e:
        print(f"❌ Erro ao salvar arquivo: {e}")

def main():
    """Função principal."""
    print(f"🔍 LISTAGEM COMPLETA DE GRUPOS - INSTÂNCIA '{evo_instance_id.upper()}'")
    print("=" * 80)
    
    # Verificar configurações
    if not evo_api_token:
        print("❌ Token da API não encontrado no arquivo .env")
        return
    
    if not evo_base_url:
        print("❌ URL da API não encontrada no arquivo .env")
        return
    
    # Listar grupos
    grupos = listar_grupos_completos()
    
    if grupos:
        # Salvar em arquivo
        salvar_grupos_arquivo(grupos)
        
        print(f"\n🎉 LISTAGEM CONCLUÍDA COM SUCESSO!")
        print(f"✅ {len(grupos)} grupos encontrados na instância {evo_instance_id}")
        print(f"💾 Dados salvos em evolution_api/tests/grupos_odisseu.json")
        
        # Instruções de uso
        print(f"\n💡 COMO USAR OS GRUPOS:")
        print(f"1. Copie o JID do grupo desejado")
        print(f"2. Use no seu arquivo .env como EVO_DESTINO_GRUPO")
        print(f"3. Exemplo: EVO_DESTINO_GRUPO=120363422140542790@g.us")
        
    else:
        print(f"\n❌ FALHA NA LISTAGEM DE GRUPOS")
        print(f"🔧 Verifique se a instância '{evo_instance_id}' existe e está conectada")

if __name__ == "__main__":
    main()
