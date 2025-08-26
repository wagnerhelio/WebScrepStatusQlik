#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import errno
from pathlib import Path
from datetime import datetime
import argparse

# Configuração para Windows - suporte a UTF-8
if os.name == 'nt':  # Windows
    try:
        # Tenta configurar o console para UTF-8
        os.system('chcp 65001 > nul')
        # Reconfigura stdout para UTF-8
        sys.stdout.reconfigure(encoding='utf-8')
    except:
        pass

# ======================
# Configuração padrão
# ======================

# Raiz do módulo = pasta do crawler (para usar crawler_qlik/errorlogs)
REPO_ROOT = Path(__file__).resolve().parent

# Diretórios A PARTIR DA RAIZ DO PROJETO (relativos). Altere se quiser.
DEFAULT_DIRS = [
    "\\\\10.242.251.28\\SSPForcas$\\SSP_FORCAS_BI\\ETLDesktop",
    "\\\\Arquivos-02\\Business Intelligence\\Qlik Sense Desktop\\ETLDesktop",
    "\\\\estatistica\\Repositorio\\ETL",
]

# Pasta/arquivo de log de erro (relativos ao projeto)
ERROR_LOG_DIR = REPO_ROOT / "errorlogs"
ERROR_LOG_PATH = ERROR_LOG_DIR / "ErrorUpdateETLDesktop.txt"


# ======================
# Utilitários
# ======================

def ensure_dir(path: Path) -> None:
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise

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

def is_network_path_accessible(path: Path) -> bool:
    """
    Verifica se um caminho de rede é acessível.
    
    Args:
        path (Path): Caminho a ser verificado
        
    Returns:
        bool: True se acessível, False caso contrário
    """
    try:
        # Normaliza o caminho antes de verificar
        path_str = str(path)
        normalized_path = normalize_unc_path(path_str)
        path = Path(normalized_path)
        
        return path.exists() and path.is_dir()
    except OSError as e:
        if e.winerror == 1326:  # Nome de usuário ou senha incorretos
            print(f"⚠️ Erro de autenticação ao verificar pasta: {path}")
            return False
        elif e.winerror == 53:  # Caminho de rede não encontrado
            print(f"⚠️ Caminho de rede não encontrado: {path}")
            return False
        elif e.winerror == 5:  # Acesso negado
            print(f"⚠️ Acesso negado ao verificar pasta: {path}")
            return False
        else:
            print(f"⚠️ Erro ao verificar pasta {path}: {e}")
            return False
    except Exception:
        return False

def list_files_recursive(root: Path):
    try:
        # Normaliza o caminho antes de verificar
        root_str = str(root)
        normalized_root = normalize_unc_path(root_str)
        root = Path(normalized_root)
        
        if not root.exists() or not root.is_dir():
            return None
        return [p for p in root.rglob("*") if p.is_file()]
    except OSError as e:
        if e.winerror == 1326:  # Nome de usuário ou senha incorretos
            print(f"⚠️ Erro de autenticação ao acessar pasta: {root}")
            print("   A pasta requer credenciais específicas de rede.")
            return None
        elif e.winerror == 53:  # Caminho de rede não encontrado
            print(f"⚠️ Caminho de rede não encontrado: {root}")
            return None
        elif e.winerror == 5:  # Acesso negado
            print(f"⚠️ Acesso negado à pasta: {root}")
            return None
        else:
            print(f"⚠️ Erro ao acessar pasta {root}: {e}")
            return None
    except Exception as e:
        print(f"⚠️ Erro inesperado ao acessar pasta {root}: {e}")
        return None

def list_files_top_level(root: Path):
    try:
        # Normaliza o caminho antes de verificar
        root_str = str(root)
        normalized_root = normalize_unc_path(root_str)
        root = Path(normalized_root)
        
        if not root.exists() or not root.is_dir():
            return None
        return [p for p in root.iterdir() if p.is_file()]
    except OSError as e:
        if e.winerror == 1326:  # Nome de usuário ou senha incorretos
            print(f"⚠️ Erro de autenticação ao acessar pasta: {root}")
            print("   A pasta requer credenciais específicas de rede.")
            return None
        elif e.winerror == 53:  # Caminho de rede não encontrado
            print(f"⚠️ Caminho de rede não encontrado: {root}")
            return None
        elif e.winerror == 5:  # Acesso negado
            print(f"⚠️ Acesso negado à pasta: {root}")
            return None
        else:
            print(f"⚠️ Erro ao acessar pasta {root}: {e}")
            return None
    except Exception as e:
        print(f"⚠️ Erro inesperado ao acessar pasta {root}: {e}")
        return None

def is_updated_today(file_path: Path, today) -> bool:
    try:
        mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
        return mtime.date() == today
    except Exception:
        return False

# ======================
# Execução
# ======================

def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Verifica se arquivos de ETL foram atualizados hoje; gera log e mostra resumo por nome (deduplicado)."
    )
    ap.add_argument(
        "--dirs", nargs="+", default=DEFAULT_DIRS,
        help="Diretórios a verificar (absolutos/UNC ou relativos)."
    )
    ap.add_argument(
        "--no-recursive", action="store_true",
        help="Não varrer recursivamente (apenas o nível da pasta)."
    )
    return ap.parse_args()

def main():
    args = parse_args()
    today = datetime.now().date()

    all_not_updated = []   # (path_str, mtime_str)
    totals = []            # (folder, total, ok, not_ok)
    missing = []           # pastas inexistentes/inacessíveis

    print("🔍 Verificando acessibilidade dos diretórios...")
    
    for d in args.dirs:
        # Normaliza o caminho antes de criar o Path
        normalized_d = normalize_unc_path(d)
        folder = Path(normalized_d)
        
        # Verifica se o diretório é acessível antes de tentar listar arquivos
        if not is_network_path_accessible(folder):
            print(f"❌ Diretório inacessível: {normalized_d}")
            missing.append(normalized_d)
            totals.append((normalized_d, 0, 0, 0))
            continue
        
        print(f"✅ Diretório acessível: {normalized_d}")
        files = list_files_top_level(folder) if args.no_recursive else list_files_recursive(folder)

        if files is None:
            missing.append(str(folder))
            totals.append((str(folder), 0, 0, 0))
            continue

        total = len(files)
        ok = 0
        not_ok = 0

        for f in files:
            if is_updated_today(f, today):
                ok += 1
            else:
                not_ok += 1
                try:
                    mtime_str = datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                except Exception:
                    mtime_str = "desconhecida"
                all_not_updated.append((str(f), mtime_str))

        totals.append((str(folder), total, ok, not_ok))

    # Resumo em tela
    print("=" * 64)
    print("Status de atualização (data de hoje):", today.strftime("%Y-%m-%d"))
    print("=" * 64)
    for folder, total, ok, not_ok in totals:
        print(f"Pasta: {folder}")
        print(f"  Arquivos encontrados : {total}")
        print(f"  Atualizados hoje     : {ok}")
        print(f"  Não atualizados      : {not_ok}")
        print()

    if missing:
        print("⚠️ Pastas inacessíveis:")
        for m in missing:
            print(f"  - {m}")
        print()

    if all_not_updated:
        print("📋 Arquivos não atualizados hoje:")
        for path, mtime in all_not_updated:
            print(f"  - {path} (última modificação: {mtime})")
        print()

    # Gera log de erro se necessário
    if all_not_updated:
        ensure_dir(ERROR_LOG_DIR)
        with open(ERROR_LOG_PATH, "w", encoding="utf-8") as f:
            f.write(f"Log gerado em: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Data de referência: {today.strftime('%Y-%m-%d')}\n")
            f.write("=" * 50 + "\n")
            for path, mtime in all_not_updated:
                f.write(f"{path} | {mtime}\n")
        print(f"📄 Log de erro salvo em: {ERROR_LOG_PATH}")
    else:
        # Remove log anterior se não há erros
        if ERROR_LOG_PATH.exists():
            ERROR_LOG_PATH.unlink()
            print("✅ Log de erro anterior removido (não há arquivos desatualizados).")

    # Resumo final
    total_files = sum(t[1] for t in totals)
    total_ok = sum(t[2] for t in totals)
    total_not_ok = sum(t[3] for t in totals)
    
    print("=" * 64)
    print("RESUMO FINAL:")
    print(f"  Total de arquivos verificados: {total_files}")
    print(f"  Arquivos atualizados hoje: {total_ok}")
    print(f"  Arquivos não atualizados: {total_not_ok}")
    print(f"  Pastas inacessíveis: {len(missing)}")
    print("=" * 64)

if __name__ == "__main__":
    main()