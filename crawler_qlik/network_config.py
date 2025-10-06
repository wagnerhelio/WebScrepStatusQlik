#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Configurações de rede para acesso a pastas compartilhadas
Permite configurar credenciais de rede para acessar pastas UNC
"""

import os
import sys
from pathlib import Path
from typing import Optional, Dict, List
import subprocess
from dotenv import load_dotenv

# Carrega variáveis de ambiente do arquivo .env
load_dotenv()

# Configuração para Windows - suporte a UTF-8
if os.name == 'nt':  # Windows
    try:
        # Tenta configurar o console para UTF-8
        os.system('chcp 65001 > nul')
        # Reconfigura stdout para UTF-8
        sys.stdout.reconfigure(encoding='utf-8')
    except:
        pass

# =============================================================================
# CONFIGURAÇÕES DE REDE
# =============================================================================

# Credenciais de rede (opcional)
NETWORK_USERNAME = os.getenv("NETWORK_USERNAME", "")
NETWORK_PASSWORD = os.getenv("NETWORK_PASSWORD", "")
NETWORK_DOMAIN = os.getenv("NETWORK_DOMAIN", "")

# Pastas de rede que requerem autenticação (lidas do .env)
NETWORK_PATHS = [
    os.getenv("NETWORK_PATH_1", ""),
    os.getenv("NETWORK_PATH_2", ""),
    os.getenv("NETWORK_PATH_3", ""),
]

# =============================================================================
# FUNÇÕES DE AUTENTICAÇÃO
# =============================================================================

def normalize_unc_path(path_str: str) -> str:
    """
    Normaliza um caminho UNC para garantir que seja interpretado corretamente.
    
    Args:
        path_str (str): Caminho UNC como string
        
    Returns:
        str: Caminho UNC normalizado
    """
    # Remove barras extras e normaliza
    path_str = path_str.replace("\\\\", "\\").replace("//", "/")
    
    # Garante que caminhos UNC tenham exatamente duas barras no início
    if path_str.startswith("\\"):
        # Se já tem uma barra, adiciona mais uma
        if not path_str.startswith("\\\\"):
            path_str = "\\" + path_str
    elif path_str.startswith("/"):
        # Se tem barra normal, converte para barra invertida
        path_str = "\\" + path_str.replace("/", "\\")
    
    return path_str

def setup_network_credentials():
    """
    Configura credenciais de rede se fornecidas.
    """
    if not NETWORK_USERNAME or not NETWORK_PASSWORD:
        print("ℹ️ Credenciais de rede não configuradas.")
        print("   Para configurar, defina as variáveis de ambiente:")
        print("   - NETWORK_USERNAME")
        print("   - NETWORK_PASSWORD") 
        print("   - NETWORK_DOMAIN (opcional)")
        return False
    
    try:
        # Tenta configurar credenciais de rede usando net use
        for path in NETWORK_PATHS:
            # Normaliza o caminho antes de usar
            normalized_path = normalize_unc_path(path)
            
            if normalized_path.startswith("\\\\"):
                server_share = normalized_path.split("\\")[2]  # Extrai servidor\share
                # Limpa o formato do usuário (remove barras duplas se existirem)
                clean_username = NETWORK_USERNAME.replace("\\\\", "\\")
                clean_domain = NETWORK_DOMAIN.replace("\\\\", "\\") if NETWORK_DOMAIN else ""
                
                cmd = [
                    "net", "use", normalized_path, 
                    f"/user:{clean_domain}\\{clean_username}" if clean_domain else f"/user:{clean_username}",
                    NETWORK_PASSWORD
                ]
                
                result = subprocess.run(
                    cmd, 
                    capture_output=True, 
                    text=True, 
                    timeout=30
                )
                
                if result.returncode == 0:
                    print(f"✅ Credenciais configuradas para: {normalized_path}")
                else:
                    print(f"⚠️ Erro ao configurar credenciais para {normalized_path}: {result.stderr.strip()}")
                    
        return True
        
    except Exception as e:
        print(f"❌ Erro ao configurar credenciais de rede: {e}")
        return False

def test_network_access():
    """
    Testa o acesso às pastas de rede configuradas.
    """
    print("🔍 Testando acesso às pastas de rede...")
    
    accessible_paths = []
    inaccessible_paths = []
    
    for path in NETWORK_PATHS:
        # Normaliza o caminho antes de testar
        normalized_path = normalize_unc_path(path)
        
        try:
            if Path(normalized_path).exists():
                accessible_paths.append(normalized_path)
                print(f"✅ Acessível: {normalized_path}")
            else:
                inaccessible_paths.append(normalized_path)
                print(f"❌ Inacessível: {normalized_path}")
        except Exception as e:
            inaccessible_paths.append(normalized_path)
            print(f"❌ Erro ao acessar {normalized_path}: {e}")
    
    print(f"\n📊 Resumo:")
    print(f"  Pastas acessíveis: {len(accessible_paths)}")
    print(f"  Pastas inacessíveis: {len(inaccessible_paths)}")
    
    return accessible_paths, inaccessible_paths

def get_accessible_paths() -> List[str]:
    """
    Retorna apenas as pastas de rede que são acessíveis.
    """
    accessible = []
    
    for path in NETWORK_PATHS:
        # Normaliza o caminho antes de testar
        normalized_path = normalize_unc_path(path)
        
        try:
            if Path(normalized_path).exists():
                accessible.append(normalized_path)
        except Exception:
            continue
    
    return accessible

# =============================================================================
# FUNÇÃO PRINCIPAL PARA TESTE
# =============================================================================

def main():
    """
    Função principal para testar configurações de rede.
    """
    print("🌐 Configuração de Rede - WebScrapStatusQlik")
    print("=" * 50)
    
    # 1. Tenta configurar credenciais se disponíveis
    if NETWORK_USERNAME and NETWORK_PASSWORD:
        print("🔐 Configurando credenciais de rede...")
        setup_network_credentials()
    else:
        print("ℹ️ Credenciais de rede não configuradas.")
    
    # 2. Testa acesso às pastas
    accessible, inaccessible = test_network_access()
    
    # 3. Sugestões
    if inaccessible:
        print("\n💡 Sugestões para resolver problemas de acesso:")
        print("   1. Verifique se as credenciais estão corretas")
        print("   2. Configure as variáveis de ambiente:")
        print("      NETWORK_USERNAME=seu_usuario")
        print("      NETWORK_PASSWORD=sua_senha")
        print("      NETWORK_DOMAIN=seu_dominio (opcional)")
        print("   3. Verifique se o servidor está acessível")
        print("   4. Teste o acesso manualmente via Windows Explorer")
    
    return len(accessible) > 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
