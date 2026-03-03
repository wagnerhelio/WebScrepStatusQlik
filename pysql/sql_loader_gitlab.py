"""
Carregador de arquivos SQL via API raw do GitLab.
Usado pelos scripts pysql_homicidios e pysql_feminicidio para obter
as queries remotamente, permitindo alterações nas SQLs sem modificar o código.
"""
from __future__ import annotations

import urllib.error
import urllib.request
from typing import Optional


def fetch_sql_from_gitlab(
    file_path: str,
    base_url: str,
    project: str,
    token: str,
    branch: str,
) -> Optional[str]:
    """
    Obtém o conteúdo de um arquivo SQL do repositório GitLab via API raw.

    Args:
        file_path: Caminho do arquivo no repositório (ex: extract_odisseu_oracle/homicidios/homicidios.sql).
        base_url: URL base do GitLab (ex: https://gitlab.ssp.go.gov.br).
        project: Caminho do projeto (ex: ssp/bi/etl-oracle). Use %2F para / na URL.
        token: Private Token de acesso à API.
        branch: Branch (ex: main).

    Returns:
        Texto da SQL em UTF-8 ou None em caso de falha (rede, 404, etc.).
    """
    base_url = base_url.rstrip("/")
    # GitLab API: project ID pode ser path URL-encoded (ex: ssp%2Fbi%2Fetl-oracle)
    from urllib.parse import quote

    project_encoded = quote(project, safe="")
    file_path_encoded = quote(file_path, safe="")
    url = (
        f"{base_url}/api/v4/projects/{project_encoded}/repository/files/{file_path_encoded}/raw?ref={quote(branch)}"
    )
    req = urllib.request.Request(url, headers={"PRIVATE-TOKEN": token})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read()
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise FileNotFoundError(f"SQL não encontrada no GitLab: {file_path}") from e
        raise RuntimeError(
            f"GitLab API erro {e.code} para {file_path}: {e.reason}"
        ) from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Falha ao acessar GitLab para {file_path}: {e.reason}") from e

    sql_text = body.decode("utf-8").strip()
    if sql_text.endswith(";"):
        sql_text = sql_text[:-1].strip()
    return sql_text


if __name__ == "__main__":
    """Teste rápido: carrega .env e busca uma SQL do GitLab."""
    import os
    from pathlib import Path
    from dotenv import load_dotenv

    project_root = Path(__file__).resolve().parent.parent
    load_dotenv(project_root / ".env")

    base = os.getenv("GITLAB_BASE_URL")
    project = os.getenv("GITLAB_PROJECT")
    token = os.getenv("GITLAB_TOKEN")
    branch = os.getenv("GITLAB_BRANCH", "main")
    path_homicidios = os.getenv("GITLAB_SQL_PATH_HOMICIDIOS", "extract_odisseu_oracle/relatorio_homicidios")
    test_path = f"{path_homicidios.rstrip('/')}/homicidios.sql"

    print("Testando sql_loader_gitlab...")
    print(f"  Base: {base}")
    print(f"  Projeto: {project}")
    print(f"  Arquivo: {test_path}")
    if not token or token == "seu_token_aqui":
        print("  ERRO: GITLAB_TOKEN não definido no .env")
        exit(1)
    try:
        sql = fetch_sql_from_gitlab(test_path, base, project, token, branch)
        if sql:
            print(f"  OK: SQL obtida ({len(sql)} caracteres)")
            print(f"  Primeiros 200 chars: {sql[:200].strip()}...")
        else:
            print("  ERRO: SQL vazia")
            exit(1)
    except Exception as e:
        print(f"  ERRO: {e}")
        exit(1)
