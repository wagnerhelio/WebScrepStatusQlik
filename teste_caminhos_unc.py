#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Script de teste para demonstrar a correção de caminhos UNC
Mostra como a normalização resolve problemas de interpretação de barras
"""

import os
from pathlib import Path

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

def test_path_interpretation():
    """
    Testa diferentes formas de interpretação de caminhos UNC.
    """
    print("🧪 Teste de Interpretação de Caminhos UNC")
    print("=" * 60)
    
    # Caminhos de teste com diferentes formatos
    test_paths = [
        # Formato correto
        "\\\\10.242.251.28\\SSPForcas$\\SSP_FORCAS_BI",
        
        # Formato com barras duplas extras (problema original)
        "\\\\\\\\10.242.251.28\\\\SSPForcas$\\\\SSP_FORCAS_BI",
        
        # Formato com barras simples
        "\\10.242.251.28\\SSPForcas$\\SSP_FORCAS_BI",
        
        # Formato com barras normais
        "//10.242.251.28/SSPForcas$/SSP_FORCAS_BI",
        
        # Formato misto
        "\\\\10.242.251.28/SSPForcas$\\SSP_FORCAS_BI",
    ]
    
    for i, path in enumerate(test_paths, 1):
        print(f"\n📁 Teste {i}: {path}")
        print(f"   Comprimento: {len(path)} caracteres")
        print(f"   Barras duplas: {path.count('\\\\')}")
        print(f"   Barras simples: {path.count('\\')}")
        
        # Normaliza o caminho
        normalized = normalize_unc_path(path)
        print(f"   ✅ Normalizado: {normalized}")
        print(f"   Comprimento normalizado: {len(normalized)} caracteres")
        
        # Testa se o caminho é válido
        try:
            path_obj = Path(normalized)
            print(f"   ✅ Path válido: {path_obj}")
            
            # Tenta verificar se existe (sem acessar realmente)
            print(f"   🔍 Tentando verificar existência...")
            exists = path_obj.exists()
            print(f"   {'✅ Existe' if exists else '❌ Não existe'}")
            
        except Exception as e:
            print(f"   ❌ Erro ao criar Path: {e}")

def test_network_access():
    """
    Testa acesso às pastas de rede reais.
    """
    print("\n🌐 Teste de Acesso às Pastas de Rede")
    print("=" * 60)
    
    network_paths = [
        "\\\\10.242.251.28\\SSPForcas$\\SSP_FORCAS_BI",
        "\\\\Arquivos-02\\Business Intelligence\\Qlik Sense Desktop",
        "\\\\estatistica\\Repositorio\\ETL",
    ]
    
    for path in network_paths:
        print(f"\n📁 Testando: {path}")
        
        try:
            # Testa sem normalização
            path_obj = Path(path)
            exists = path_obj.exists()
            print(f"   Sem normalização: {'✅ Acessível' if exists else '❌ Inacessível'}")
            
        except Exception as e:
            print(f"   Sem normalização: ❌ Erro - {e}")
        
        try:
            # Testa com normalização
            normalized = normalize_unc_path(path)
            path_obj = Path(normalized)
            exists = path_obj.exists()
            print(f"   Com normalização: {'✅ Acessível' if exists else '❌ Inacessível'}")
            
        except Exception as e:
            print(f"   Com normalização: ❌ Erro - {e}")

def main():
    """
    Função principal do teste.
    """
    print("🔧 Teste de Correção de Caminhos UNC")
    print("=" * 60)
    print("Este script demonstra como a normalização resolve problemas")
    print("de interpretação de caminhos UNC em diferentes sistemas.\n")
    
    # Teste 1: Interpretação de caminhos
    test_path_interpretation()
    
    # Teste 2: Acesso real às pastas
    test_network_access()
    
    print("\n" + "=" * 60)
    print("✅ Teste concluído!")
    print("💡 A normalização garante que os caminhos sejam interpretados")
    print("   corretamente em diferentes ambientes Windows.")

if __name__ == "__main__":
    main()
