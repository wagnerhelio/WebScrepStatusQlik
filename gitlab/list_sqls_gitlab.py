#!/usr/bin/env python3
"""
Lista todos os arquivos .sql do repositório GitLab (etl-oracle) e gera sqls_gitlab.json.

Uso (na raiz do projeto, com .env configurado):
  python gitlab/list_sqls_gitlab.py

Variáveis de ambiente (.env na raiz):
  GITLAB_BASE_URL  - URL base (ex: https://gitlab.ssp.go.gov.br)
  GITLAB_PROJECT   - Projeto (ex: ssp/bi/etl-oracle)
  GITLAB_TOKEN     - Private Token da API
  GITLAB_BRANCH    - Branch (ex: main)

Saída: gitlab/sqls_gitlab.json, com estrutura por diretório e raw_url para cada SQL.
Exemplo de raw_url:
  https://gitlab.ssp.go.gov.br/ssp/bi/etl-oracle/-/raw/main/extract_odisseu_oracle/relatorio_homicidios/homicidios.sql
"""

import os
import sys
import json
import requests
from pathlib import Path
from dotenv import load_dotenv

# UTF-8 no Windows
if os.name == "nt":
    try:
        os.system("chcp 65001 > nul")
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Script está em gitlab/; .env fica na raiz do repositório
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
load_dotenv(PROJECT_ROOT / ".env")

GITLAB_BASE_URL = os.getenv("GITLAB_BASE_URL", "https://gitlab.ssp.go.gov.br").rstrip("/")
GITLAB_PROJECT = os.getenv("GITLAB_PROJECT", "ssp/bi/etl-oracle")
GITLAB_TOKEN = os.getenv("GITLAB_TOKEN")
GITLAB_BRANCH = os.getenv("GITLAB_BRANCH", "main")
OUTPUT_JSON = SCRIPT_DIR / "sqls_gitlab.json"


def build_raw_url(path: str) -> str:
    """Monta a URL raw de um arquivo no GitLab."""
    return f"{GITLAB_BASE_URL}/{GITLAB_PROJECT}/-/raw/{GITLAB_BRANCH}/{path}"


def list_sqls_from_gitlab():
    """Obtém a árvore do repositório (todas as páginas) e filtra arquivos .sql."""
    project_encoded = requests.utils.quote(GITLAB_PROJECT, safe="")
    url = f"{GITLAB_BASE_URL}/api/v4/projects/{project_encoded}/repository/tree"
    per_page = 100  # máximo permitido pela API GitLab
    headers = {"PRIVATE-TOKEN": GITLAB_TOKEN}
    all_items = []
    page = 1
    while True:
        params = {
            "recursive": "true",
            "ref": GITLAB_BRANCH,
            "per_page": per_page,
            "page": page,
        }
        r = requests.get(url, headers=headers, params=params, timeout=60)
        if r.status_code != 200:
            raise RuntimeError(f"GitLab API: {r.status_code} - {r.text[:300]}")
        data = r.json()
        all_items.extend(data)
        # GitLab usa o header X-Next-Page para indicar a próxima página (vazio = última)
        next_page = r.headers.get("X-Next-Page", "").strip()
        if not next_page:
            break
        try:
            page = int(next_page)
        except ValueError:
            break
        if not data:
            break

    sqls = [x for x in all_items if x.get("type") == "blob" and (x.get("path") or "").endswith(".sql")]
    return sqls


def main():
    print("=" * 70)
    print("Listando SQLs do GitLab e gerando sqls_gitlab.json")
    print("=" * 70)
    print(f"Base: {GITLAB_BASE_URL}")
    print(f"Projeto: {GITLAB_PROJECT}")
    print(f"Branch: {GITLAB_BRANCH}")
    print()

    if not GITLAB_TOKEN or GITLAB_TOKEN == "seu_token_aqui":
        print("Defina GITLAB_TOKEN no .env (Private Token do GitLab).")
        return 1

    try:
        items = list_sqls_from_gitlab()
    except Exception as e:
        print(f"Erro ao listar repositório: {e}")
        return 1

    if not items:
        print("Nenhum arquivo .sql encontrado no repositório.")
        # Escreve JSON vazio para não quebrar quem lê o arquivo
        with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
            json.dump({}, f, indent=2, ensure_ascii=False)
        return 0

    # Agrupa por diretório (caminho completo da pasta que contém o .sql)
    by_dir = {}
    for item in items:
        path = item.get("path", "")
        name = item.get("name", "")
        raw_url = build_raw_url(path)
        # Diretório sempre com / (GitLab usa /; Path no Windows geraria \)
        dir_path = "/".join(Path(path).parts[:-1]) if Path(path).parts else path
        if dir_path not in by_dir:
            by_dir[dir_path] = []
        by_dir[dir_path].append({
            "name": name,
            "path": path,
            "raw_url": raw_url,
        })

    # Ordena diretórios e itens para saída estável
    out = {}
    for key in sorted(by_dir.keys()):
        out[key] = sorted(by_dir[key], key=lambda x: (x["path"], x["name"]))

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    total = sum(len(v) for v in out.values())
    print(f"Total de arquivos .sql listados: {total}")
    print(f"Diretórios com .sql: {len(out)}")
    for d in sorted(out.keys()):
        print(f"  - {d}: {len(out[d])} arquivo(s)")
    print(f"Arquivo gerado: {OUTPUT_JSON}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
