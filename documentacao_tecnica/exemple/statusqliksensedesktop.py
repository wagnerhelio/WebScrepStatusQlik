import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests


REPO_OWNER = "qlik-download"
REPO_NAME = "qlik-sense-desktop"
GITHUB_API_BASE = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}"


TARGET_ROOTS = [
    r"\\10.242.251.28\SSPForcas$\SSP_FORCAS_BI",
    r"\\Arquivos-02\Business Intelligence\Qlik Sense Desktop",
]


def build_session() -> requests.Session:
    session = requests.Session()
    token = os.getenv("GITHUB_TOKEN")
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "WebScrepStatusQlik/1.0",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    session.headers.update(headers)
    return session


def get_latest_release(session: requests.Session) -> Dict:
    url = f"{GITHUB_API_BASE}/releases/latest"
    resp = session.get(url, timeout=60)
    resp.raise_for_status()
    return resp.json()


def extract_month_year(release_name: str) -> Optional[Tuple[str, str]]:
    # Examples: "May 2025 Patch 3", "November 2024 Patch 12"
    m = re.match(r"^(?P<month>[A-Za-z]+)\s+(?P<year>\d{4})\b", release_name.strip())
    if not m:
        return None
    return m.group("month"), m.group("year")


def list_releases(session: requests.Session, per_page: int = 100, max_pages: int = 10) -> List[Dict]:
    releases: List[Dict] = []
    for page in range(1, max_pages + 1):
        url = f"{GITHUB_API_BASE}/releases?per_page={per_page}&page={page}"
        resp = session.get(url, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        if not data:
            break
        releases.extend(data)
    return releases


def find_initial_release(session: requests.Session, month: str, year: str) -> Optional[Dict]:
    target_name = f"{month} {year} Initial Release"
    for rel in list_releases(session):
        name = (rel.get("name") or rel.get("tag_name") or "").strip()
        if name == target_name:
            return rel
    # Fallback: try case-insensitive exact match
    for rel in list_releases(session):
        name = (rel.get("name") or rel.get("tag_name") or "").strip()
        if name.lower() == target_name.lower():
            return rel
    # Fallback: contains and startswith heuristics
    for rel in list_releases(session):
        name = (rel.get("name") or rel.get("tag_name") or "").strip()
        if name.startswith(f"{month} {year}") and "Initial" in name:
            return rel
    return None


def ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def download_asset(session: requests.Session, url: str, dest_file: Path) -> None:
    with session.get(url, stream=True, timeout=300) as r:
        r.raise_for_status()
        with open(dest_file, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)


def download_release_assets(session: requests.Session, release: Dict, dest_dir: Path) -> List[Path]:
    assets = release.get("assets") or []
    saved_files: List[Path] = []
    if not assets:
        return saved_files
    ensure_directory(dest_dir)
    for asset in assets:
        asset_name = asset.get("name") or "download.bin"
        download_url = asset.get("browser_download_url") or asset.get("url")
        if not download_url:
            continue
        target = dest_dir / asset_name
        print(f"Baixando: {asset_name} -> {target}")
        try:
            download_asset(session, download_url, target)
            saved_files.append(target)
        except Exception as e:
            print(f"Falha ao baixar {asset_name}: {e}")
    return saved_files


def main() -> int:
    print("Iniciando busca de releases no GitHub...")
    session = build_session()

    try:
        latest = get_latest_release(session)
    except Exception as e:
        print(f"Erro ao obter o 'Latest' release: {e}")
        return 1

    latest_name = (latest.get("name") or latest.get("tag_name") or "Latest").strip()
    print(f"Release mais recente: {latest_name}")

    month_year = extract_month_year(latest_name)
    if not month_year:
        print("Não foi possível extrair mês e ano do nome do release mais recente.")
        return 1
    month, year = month_year

    try:
        initial_release = find_initial_release(session, month, year)
    except Exception as e:
        print(f"Erro ao procurar o 'Initial Release' de {month} {year}: {e}")
        return 1

    if not initial_release:
        print(f"Initial Release de {month} {year} não encontrado.")
        return 1

    initial_name = (initial_release.get("name") or initial_release.get("tag_name") or "Initial Release").strip()
    print(f"Initial Release encontrado: {initial_name}")

    # Criar as pastas-alvo e preparar alvos de download
    download_targets: List[Tuple[Dict, Path, str]] = []
    for root in TARGET_ROOTS:
        latest_dir = Path(root) / f"{latest_name} - Latest"
        initial_dir = Path(root) / initial_name
        try:
            ensure_directory(latest_dir)
            print(f"Pasta criada/confirmada: {latest_dir}")
            ensure_directory(initial_dir)
            print(f"Pasta criada/confirmada: {initial_dir}")
            download_targets.append((latest, latest_dir, "Latest"))
            download_targets.append((initial_release, initial_dir, "Initial Release"))
        except Exception as e:
            print(f"Falha ao criar diretórios em '{root}': {e}")

    if not download_targets:
        print("Nenhuma pasta válida foi criada. Verifique o acesso às pastas de rede.")
        return 1

    # Baixar os assets de cada release para seus respectivos destinos
    total_saved = 0
    for release_obj, dest, label in download_targets:
        print(f"Baixando assets do {label} para: {dest}")
        saved_files = download_release_assets(session, release_obj, dest)
        total_saved += len(saved_files)

    if total_saved == 0:
        print("Nenhum asset foi baixado. Verifique se o release possui assets públicos.")
        return 2

    print(f"Concluído. Total de arquivos baixados: {total_saved}")
    return 0


if __name__ == "__main__":
    sys.exit(main())


