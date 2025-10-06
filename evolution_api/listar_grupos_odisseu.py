#!/usr/bin/env python3
"""
Script para listar todos os grupos da instância odisseu com JID e nome
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

# Carrega variáveis de ambiente
load_dotenv()

# Configurações da Evolution API
evo_base_url = os.getenv("EVOLUTION_BASE_URL", "http://localhost:8080")
evo_api_token = os.getenv("EVOLUTION_API_TOKEN")
evo_instance_id = "odisseu"

def listar_grupos_completos():
    """Lista todos os grupos com informações completas."""
    print("🔍 LISTANDO GRUPOS DA INSTÂNCIA ODISSEU")
    print("=" * 70)
    
    url = f"{evo_base_url}/group/fetchAllGroups/{evo_instance_id}?getParticipants=true"
    headers = {
        "apikey": evo_api_token,
        "Content-Type": "application/json"
    }
    
    print(f"🌐 URL: {url}")
    print(f"🔑 API Token: {evo_api_token[:10]}...")
    print(f"📱 Instância: {evo_instance_id}")
    
    try:
        print("\n📡 Fazendo requisição para a API...")
        response = requests.get(url, headers=headers, timeout=30)
        
        print(f"📊 Status HTTP: {response.status_code}")
        
        if response.status_code == 200:
            grupos = response.json()
            print(f"✅ SUCESSO! Total de grupos encontrados: {len(grupos)}")
            
            if len(grupos) == 0:
                print("⚠️ Nenhum grupo encontrado na instância odisseu")
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
            return None
            
    except Exception as e:
        print(f"❌ Erro na requisição: {e}")
        import traceback
        print(f"🔍 Traceback: {traceback.format_exc()}")
        return None

def salvar_grupos_arquivo(grupos):
    """Salva a lista de grupos em arquivo JSON."""
    if not grupos:
        return
    
    try:
        arquivo = "grupos_odisseu.json"
        with open(arquivo, 'w', encoding='utf-8') as f:
            json.dump(grupos, f, indent=2, ensure_ascii=False)
        print(f"\n💾 Lista de grupos salva em: {arquivo}")
    except Exception as e:
        print(f"❌ Erro ao salvar arquivo: {e}")

def main():
    """Função principal."""
    print("🔍 LISTAGEM COMPLETA DE GRUPOS - INSTÂNCIA ODISSEU")
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
        print(f"✅ {len(grupos)} grupos encontrados na instância odisseu")
        print(f"💾 Dados salvos em 'grupos_odisseu.json'")
        
        # Instruções de uso
        print(f"\n💡 COMO USAR OS GRUPOS:")
        print(f"1. Copie o JID do grupo desejado")
        print(f"2. Use no seu arquivo .env como EVO_DESTINO_GRUPO")
        print(f"3. Exemplo: EVO_DESTINO_GRUPO=120363422140542790@g.us")
        
    else:
        print(f"\n❌ FALHA NA LISTAGEM DE GRUPOS")
        print(f"🔧 Verifique se a instância odisseu está funcionando")

if __name__ == "__main__":
    main()
