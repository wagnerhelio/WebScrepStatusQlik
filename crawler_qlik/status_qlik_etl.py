#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import errno
from pathlib import Path
from datetime import datetime
import argparse

# ======================
# Configuração padrão
# ======================

# Raiz do módulo = pasta do crawler (para usar crawler_qlik/errorlogs)
REPO_ROOT = Path(__file__).resolve().parent

# Diretórios A PARTIR DA RAIZ DO PROJETO (relativos). Altere se quiser.
DEFAULT_DIRS = [
    r"\\10.242.251.28\SSPForcas$\SSP_FORCAS_BI\ETLDesktop",
    r"\\Arquivos-02\Business Intelligence\Qlik Sense Desktop\ETLDesktop",
    r"\\estatistica\Repositorio\ETL",
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

def list_files_recursive(root: Path):
    if not root.exists() or not root.is_dir():
        return None
    return [p for p in root.rglob("*") if p.is_file()]

def list_files_top_level(root: Path):
    if not root.exists() or not root.is_dir():
        return None
    return [p for p in root.iterdir() if p.is_file()]

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

    for d in args.dirs:
        folder = Path(d)
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
        print(f"  NÃO atualizados      : {not_ok}")
        print("-" * 64)

    if missing:
        print("Pastas inexistentes ou inacessíveis:")
        for m in missing:
            print(f"  - {m}")
        print("-" * 64)

    if all_not_updated:
        # grava arquivo de log detalhado (com caminhos completos)
        ensure_dir(ERROR_LOG_DIR)
        with open(ERROR_LOG_PATH, "w", encoding="utf-8") as f:
            f.write(f"Arquivos NÃO atualizados em {today.strftime('%Y-%m-%d')}\n")
            f.write("=" * 64 + "\n")
            for path_str, mtime in all_not_updated:
                f.write(f"{path_str} ; modificado em: {mtime}\n")

        print(f"ATENÇÃO: {len(all_not_updated)} arquivo(s) não foram atualizados hoje.")
        print(f"Detalhes em: {ERROR_LOG_PATH}")

        # ===== RESUMO DEDUPLICADO POR NOME =====
        unique_names = {}
        for path_str, _ in all_not_updated:
            name = Path(path_str).name
            key = name.lower()  # dedupe case-insensitive (Windows)
            if key not in unique_names:
                unique_names[key] = name  # preserva a 1ª grafia

        print(f"Resumo por NOME (único): {len(unique_names)} arquivo(s) não atualizados:")
        for name in sorted(unique_names.values(), key=str.lower):
            print(f"  - {name}")
    else:
        print("Tudo OK: todos os arquivos analisados foram atualizados hoje.")
    print("=" * 64)

if __name__ == "__main__":
    main()