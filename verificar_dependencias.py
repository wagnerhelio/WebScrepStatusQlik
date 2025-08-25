#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Script de verificação de dependências do projeto WebScrapStatusQlik
Verifica se todas as bibliotecas necessárias estão instaladas e funcionando
"""

import sys
import subprocess
import importlib
from pathlib import Path

# Lista de dependências principais organizadas por categoria
DEPENDENCIAS = {
    "Automação Web": [
        "selenium",
        "beautifulsoup4", 
        "requests",
        "lxml"
    ],
    "Banco de Dados": [
        "oracledb",
        "cx_Oracle"
    ],
    "Análise de Dados": [
        "pandas",
        "numpy",
        "matplotlib",
        "seaborn",
        "openpyxl"
    ],
    "Geração de Relatórios": [
        "fpdf",
        "reportlab",
        "xhtml2pdf",
        "weasyprint",
        "pdfkit",
        "pypdf"
    ],
    "Comunicação e API": [
        "evolutionapi",
        "python-engineio",
        "python-socketio",
        "websocket-client"
    ],
    "Utilitários": [
        "python-dotenv",
        "colorama",
        "tqdm",
        "schedule",
        "PyYAML"
    ],
    "Processamento de Texto": [
        "chardet",
        "charset-normalizer",
        "arabic-reshaper",
        "python-bidi"
    ],
    "Criptografia": [
        "cryptography",
        "asn1crypto",
        "cffi"
    ]
}

def verificar_import(module_name):
    """
    Verifica se um módulo pode ser importado.
    
    Args:
        module_name (str): Nome do módulo
        
    Returns:
        tuple: (bool, str) - (sucesso, mensagem)
    """
    try:
        importlib.import_module(module_name)
        return True, f"✅ {module_name}"
    except ImportError as e:
        return False, f"❌ {module_name}: {e}"
    except Exception as e:
        return False, f"⚠️ {module_name}: {e}"

def verificar_versao_python():
    """Verifica a versão do Python."""
    version = sys.version_info
    if version.major >= 3 and version.minor >= 8:
        return True, f"✅ Python {version.major}.{version.minor}.{version.micro}"
    else:
        return False, f"❌ Python {version.major}.{version.minor}.{version.micro} (requer 3.8+)"

def verificar_chromedriver():
    """Verifica se o ChromeDriver está disponível."""
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.service import Service
        
        # Tenta encontrar o ChromeDriver
        chromedriver_paths = [
            "crawler_qlik/chromedriver/chromedriver.exe",  # Windows
            "crawler_qlik/chromedriver/chromedriver",      # Linux/macOS
            "chromedriver.exe",                            # PATH Windows
            "chromedriver"                                 # PATH Linux/macOS
        ]
        
        for path in chromedriver_paths:
            if Path(path).exists():
                return True, f"✅ ChromeDriver encontrado: {path}"
        
        return False, "❌ ChromeDriver não encontrado"
        
    except Exception as e:
        return False, f"❌ Erro ao verificar ChromeDriver: {e}"

def verificar_oracle_client():
    """Verifica se o Oracle Client está configurado."""
    try:
        import oracledb
        return True, "✅ Oracle Client configurado"
    except ImportError:
        return False, "❌ Oracle Client não encontrado"
    except Exception as e:
        return False, f"⚠️ Oracle Client: {e}"

def verificar_arquivo_env():
    """Verifica se o arquivo .env existe."""
    env_file = Path(".env")
    if env_file.exists():
        return True, "✅ Arquivo .env encontrado"
    else:
        return False, "❌ Arquivo .env não encontrado (copie .env_exemple para .env)"

def verificar_ambiente_virtual():
    """Verifica se está em um ambiente virtual."""
    if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        return True, "✅ Ambiente virtual ativo"
    else:
        return False, "⚠️ Ambiente virtual não detectado (recomendado)"

def main():
    """Função principal de verificação."""
    print("🔍 Verificação de Dependências - WebScrapStatusQlik")
    print("=" * 60)
    
    # Verificações básicas
    print("\n📋 Verificações Básicas:")
    print("-" * 30)
    
    # Python
    success, msg = verificar_versao_python()
    print(msg)
    
    # Ambiente virtual
    success, msg = verificar_ambiente_virtual()
    print(msg)
    
    # Arquivo .env
    success, msg = verificar_arquivo_env()
    print(msg)
    
    # ChromeDriver
    success, msg = verificar_chromedriver()
    print(msg)
    
    # Oracle Client
    success, msg = verificar_oracle_client()
    print(msg)
    
    # Verificação de dependências Python
    print("\n📦 Verificação de Dependências Python:")
    print("-" * 40)
    
    total_deps = 0
    deps_ok = 0
    
    for categoria, modulos in DEPENDENCIAS.items():
        print(f"\n🔹 {categoria}:")
        for modulo in modulos:
            total_deps += 1
            success, msg = verificar_import(modulo)
            if success:
                deps_ok += 1
            print(f"  {msg}")
    
    # Resumo
    print("\n" + "=" * 60)
    print("📊 RESUMO:")
    print(f"  Dependências verificadas: {total_deps}")
    print(f"  Dependências OK: {deps_ok}")
    print(f"  Dependências com problema: {total_deps - deps_ok}")
    
    if deps_ok == total_deps:
        print("\n🎉 Todas as dependências estão instaladas corretamente!")
        print("✅ O projeto está pronto para uso.")
    else:
        print(f"\n⚠️ {total_deps - deps_ok} dependência(s) com problema.")
        print("💡 Execute: pip install -r requirements.txt")
    
    # Sugestões
    print("\n💡 Sugestões:")
    print("  - Para instalar dependências: pip install -r requirements.txt")
    print("  - Para atualizar dependências: pip install -r requirements.txt --upgrade")
    print("  - Para verificar versões: pip list")
    print("  - Para ambiente virtual: python -m venv venv")
    
    return deps_ok == total_deps

if __name__ == "__main__":
    try:
        sucesso = main()
        sys.exit(0 if sucesso else 1)
    except KeyboardInterrupt:
        print("\n\n⏹️ Verificação interrompida pelo usuário.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Erro durante a verificação: {e}")
        sys.exit(1)
