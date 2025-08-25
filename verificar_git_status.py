#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Script para verificar o status do Git e identificar arquivos que não estão sendo rastreados
"""

import subprocess
import os
from pathlib import Path

def executar_comando_git(comando):
    """Executa um comando Git e retorna o resultado."""
    try:
        resultado = subprocess.run(
            comando, 
            shell=True, 
            capture_output=True, 
            text=True, 
            cwd=os.getcwd()
        )
        return resultado.stdout.strip(), resultado.stderr.strip(), resultado.returncode
    except Exception as e:
        return "", str(e), 1

def verificar_status_git():
    """Verifica o status atual do Git."""
    print("🔍 Verificando Status do Git")
    print("=" * 50)
    
    # Status geral
    stdout, stderr, code = executar_comando_git("git status")
    if code == 0:
        print("📋 Status Geral:")
        print(stdout)
    else:
        print(f"❌ Erro ao verificar status: {stderr}")
        return False
    
    return True

def listar_arquivos_nao_rastreados():
    """Lista arquivos que não estão sendo rastreados pelo Git."""
    print("\n📁 Arquivos Não Rastreados:")
    print("-" * 30)
    
    # Arquivos não rastreados (não ignorados)
    stdout, stderr, code = executar_comando_git("git ls-files --others --exclude-standard")
    if code == 0 and stdout:
        arquivos_nao_rastreados = stdout.split('\n')
        print(f"✅ Encontrados {len(arquivos_nao_rastreados)} arquivos não rastreados:")
        for arquivo in arquivos_nao_rastreados:
            if arquivo.strip():
                print(f"  📄 {arquivo}")
    else:
        print("ℹ️ Nenhum arquivo não rastreado encontrado")
    
    # Arquivos ignorados
    print("\n🚫 Arquivos Ignorados:")
    print("-" * 20)
    stdout, stderr, code = executar_comando_git("git ls-files --others --ignored --exclude-standard")
    if code == 0 and stdout:
        arquivos_ignorados = stdout.split('\n')
        print(f"⚠️ Encontrados {len(arquivos_ignorados)} arquivos ignorados:")
        # Mostra apenas os primeiros 10 para não poluir a saída
        for i, arquivo in enumerate(arquivos_ignorados[:10]):
            if arquivo.strip():
                print(f"  🚫 {arquivo}")
        if len(arquivos_ignorados) > 10:
            print(f"  ... e mais {len(arquivos_ignorados) - 10} arquivos ignorados")
    else:
        print("ℹ️ Nenhum arquivo ignorado encontrado")

def listar_arquivos_modificados():
    """Lista arquivos que foram modificados."""
    print("\n📝 Arquivos Modificados:")
    print("-" * 25)
    
    stdout, stderr, code = executar_comando_git("git status --porcelain")
    if code == 0 and stdout:
        linhas = stdout.split('\n')
        arquivos_modificados = [linha for linha in linhas if linha.strip()]
        print(f"🔄 Encontrados {len(arquivos_modificados)} arquivos modificados:")
        for linha in arquivos_modificados:
            status = linha[:2]
            arquivo = linha[3:]
            if status == "M ":
                print(f"  📝 Modificado: {arquivo}")
            elif status == " M":
                print(f"  📝 Modificado (não commitado): {arquivo}")
            elif status == "??":
                print(f"  ➕ Novo: {arquivo}")
            elif status == "A ":
                print(f"  ➕ Adicionado: {arquivo}")
            else:
                print(f"  ❓ {status}: {arquivo}")
    else:
        print("ℹ️ Nenhum arquivo modificado encontrado")

def verificar_arquivos_importantes():
    """Verifica se arquivos importantes estão sendo rastreados."""
    print("\n🎯 Verificando Arquivos Importantes:")
    print("-" * 35)
    
    arquivos_importantes = [
        "requirements.txt",
        "README.md",
        "INSTALACAO.md",
        "SOLUCAO_ERRO_REDE.md",
        "RESUMO_ATUALIZACOES.md",
        "verificar_dependencias.py",
        "teste_caminhos_unc.py",
        "crawler_qlik/network_config.py",
        "crawler_qlik/status_qlik_desktop.py",
        "crawler_qlik/status_qlik_etl.py",
        "evolution_api/send_qlik_evolution.py",
        ".env_exemple"
    ]
    
    for arquivo in arquivos_importantes:
        if os.path.exists(arquivo):
            stdout, stderr, code = executar_comando_git(f"git ls-files {arquivo}")
            if code == 0 and stdout.strip():
                print(f"  ✅ {arquivo} - Rastreado")
            else:
                print(f"  ❌ {arquivo} - NÃO rastreado")
        else:
            print(f"  ⚠️ {arquivo} - Não existe")

def sugerir_comandos():
    """Sugere comandos para adicionar arquivos ao Git."""
    print("\n💡 Sugestões de Comandos:")
    print("-" * 25)
    
    print("Para adicionar todos os arquivos não rastreados:")
    print("  git add .")
    print()
    
    print("Para adicionar arquivos específicos:")
    print("  git add requirements.txt")
    print("  git add INSTALACAO.md")
    print("  git add RESUMO_ATUALIZACOES.md")
    print("  git add verificar_dependencias.py")
    print("  git add teste_caminhos_unc.py")
    print()
    
    print("Para verificar o que será commitado:")
    print("  git status")
    print()
    
    print("Para fazer commit das mudanças:")
    print("  git commit -m \"Atualização: novos arquivos e documentação\"")
    print()
    
    print("Para enviar para o repositório remoto:")
    print("  git push origin main")

def main():
    """Função principal."""
    print("🔍 Verificação Completa do Status do Git")
    print("=" * 50)
    
    # Verifica se estamos em um repositório Git
    stdout, stderr, code = executar_comando_git("git rev-parse --git-dir")
    if code != 0:
        print("❌ Erro: Não estamos em um repositório Git!")
        print("💡 Execute: git init")
        return False
    
    # Executa todas as verificações
    verificar_status_git()
    listar_arquivos_nao_rastreados()
    listar_arquivos_modificados()
    verificar_arquivos_importantes()
    sugerir_comandos()
    
    print("\n" + "=" * 50)
    print("✅ Verificação concluída!")
    
    return True

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⏹️ Verificação interrompida pelo usuário.")
    except Exception as e:
        print(f"\n❌ Erro durante a verificação: {e}")
