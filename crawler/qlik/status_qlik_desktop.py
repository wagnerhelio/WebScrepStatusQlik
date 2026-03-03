#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import sys
import json
import time
import errno
import argparse
from pathlib import Path
from typing import Dict, List, Optional
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from datetime import datetime, timezone
import shutil
import tempfile
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

# =========================
# CONFIGURAÇÕES DO USUÁRIO
# =========================

REPO_OWNER = "qlik-download"
REPO_NAME = "qlik-sense-desktop"

# Credenciais de rede (opcional)
NETWORK_USERNAME = os.getenv("NETWORK_USERNAME", "")
NETWORK_PASSWORD = os.getenv("NETWORK_PASSWORD", "")
NETWORK_DOMAIN = os.getenv("NETWORK_DOMAIN", "")

# Caminhos de destino (UNC) — lidos do arquivo .env
DESTINATION_BASE_DIRS = [
    os.getenv("NETWORK_PATH_1", ""),
    os.getenv("NETWORK_PATH_2", ""),
    os.getenv("NETWORK_PATH_3", ""),
]

# Remove caminhos vazios da lista
DESTINATION_BASE_DIRS = [path for path in DESTINATION_BASE_DIRS if path.strip()]

# Verifica se pelo menos um caminho está configurado
if not DESTINATION_BASE_DIRS:
    print("⚠️ Nenhum caminho de rede configurado no arquivo .env")
    print("   Configure pelo menos uma das variáveis:")
    print("   - NETWORK_PATH_1")
    print("   - NETWORK_PATH_2") 
    print("   - NETWORK_PATH_3")
    sys.exit(1)

HTTP_TIMEOUT = 60
DOWNLOAD_RETRIES = 3
RETRY_SLEEP_SECONDS = 3


# ============
# UTILITÁRIOS
# ============

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
        for path in DESTINATION_BASE_DIRS:
            if not path.strip():
                continue
                
            # Normaliza o caminho antes de usar
            normalized_path = normalize_unc_path(path)
            
            if normalized_path.startswith("\\\\"):
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

def print_header():
    print("=" * 68)
    print("Qlik Sense Desktop - Downloader (Initial + Latest | sem cache/log)")
    print("=" * 68)

def ensure_dir(path: Path) -> None:
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        if e.errno != errno.EEXIST:
            # Tratamento específico para erros de autenticação de rede
            if e.winerror == 1326:  # Nome de usuário ou senha incorretos
                print(f"⚠️ Erro de autenticação ao acessar pasta de rede: {path}")
                print("   A pasta requer credenciais específicas de rede.")
                print("   Pulando esta pasta e continuando...")
                return
            elif e.winerror == 53:  # Caminho de rede não encontrado
                print(f"⚠️ Caminho de rede não encontrado: {path}")
                print("   Verifique se o servidor está acessível.")
                print("   Pulando esta pasta e continuando...")
                return
            elif e.winerror == 5:  # Acesso negado
                print(f"⚠️ Acesso negado à pasta: {path}")
                print("   Verifique as permissões de acesso.")
                print("   Pulando esta pasta e continuando...")
                return
            else:
                print(f"⚠️ Erro ao acessar pasta {path}: {e}")
                print("   Pulando esta pasta e continuando...")
                return

def sanitize_filename(name: str) -> str:
    return re.sub(r'[<>:\"/\\|?*\x00-\x1F]', "_", (name or "")).strip()

def parse_github_ts(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    try:
        if ts.endswith("Z"):
            ts = ts.replace("Z", "+00:00")
        return datetime.fromisoformat(ts).astimezone(timezone.utc)
    except Exception:
        return None

def get_local_mtime(path: Path) -> Optional[datetime]:
    try:
        ts = path.stat().st_mtime
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    except FileNotFoundError:
        return None

def set_local_mtime(path: Path, dt: Optional[datetime]) -> None:
    if dt is None:
        return
    ts = dt.timestamp()
    try:
        os.utime(path, (ts, ts))
    except Exception:
        pass


# =================
# GITHUB / RELEASES
# =================

def build_headers() -> Dict[str, str]:
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "qs-desktop-simple"}
    token = os.getenv("GITHUB_TOKEN")  # opcional; evita rate limit
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers

def http_get_json(url: str) -> dict:
    req = Request(url, headers=build_headers())
    with urlopen(req, timeout=HTTP_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))

def get_latest_release() -> dict:
    return http_get_json(f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/releases/latest")

def get_all_releases(per_page: int = 80) -> List[dict]:
    return http_get_json(f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/releases?per_page={per_page}")

def extract_cycle_from_name(release_name: str) -> Optional[str]:
    parts = (release_name or "").split()
    if len(parts) >= 2 and parts[1].isdigit():
        return f"{parts[0]} {parts[1]}"
    return None

def find_initial_release_for_cycle(all_releases: List[dict], cycle: str) -> Optional[dict]:
    cands = []
    for r in all_releases:
        name = (r.get("name") or "").strip()
        if name.startswith(cycle) and "initial release" in name.lower():
            if not r.get("draft") and not r.get("prerelease"):
                cands.append(r)
    if not cands:
        return None
    cands.sort(key=lambda r: r.get("published_at") or r.get("created_at") or "", reverse=True)
    return cands[0]


# =========================
# DOWNLOAD / CÓPIA DIRETOS
# =========================

def http_download_to_temp(url: str, remote_updated_at: Optional[datetime], display_name: str) -> Path:
    """
    Baixa uma única vez para arquivo temporário e retorna o caminho.
    Mostra porcentagem se Content-Length estiver disponível.
    """
    attempt = 0
    while attempt < DOWNLOAD_RETRIES:
        attempt += 1
        try:
            req = Request(url, headers=build_headers())
            with urlopen(req, timeout=HTTP_TIMEOUT) as resp:
                # tenta obter o tamanho total
                length = resp.getheader("Content-Length")
                total = int(length) if length and length.isdigit() else None

                fd, tmp_path = tempfile.mkstemp(prefix="qsdl_", suffix=".bin")
                os.close(fd)
                tmp = Path(tmp_path)

                bytes_done = 0
                chunk_size = 1024 * 256
                with open(tmp, "wb") as f:
                    while True:
                        chunk = resp.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        bytes_done += len(chunk)
                        if total:
                            pct = bytes_done * 100 // total
                            sys.stdout.write(f"\r  → {display_name} [{pct}%]")
                        else:
                            # fallback: mostra bytes quando não há tamanho total
                            sys.stdout.write(f"\r  → {display_name} [{bytes_done} bytes]")
                        sys.stdout.flush()
                # fim da linha de progresso
                if total:
                    sys.stdout.write(f"\r  → {display_name} [100%]\n")
                else:
                    sys.stdout.write("\n")
                set_local_mtime(tmp, remote_updated_at)
                return tmp
        except (HTTPError, URLError, TimeoutError) as e:
            if attempt < DOWNLOAD_RETRIES:
                time.sleep(RETRY_SLEEP_SECONDS)
            else:
                raise RuntimeError(f"Falha ao baixar {url}: {e}")

def files_equal_by_size_and_date(path: Path, remote_size: Optional[int], remote_updated_at: Optional[datetime]) -> bool:
    if not path.exists():
        return False
    try:
        if remote_size is not None and path.stat().st_size != remote_size:
            return False
        local_mtime = get_local_mtime(path)
        if remote_updated_at and local_mtime and local_mtime < remote_updated_at:
            return False
        return True
    except Exception:
        return False

def copy2_preserve(src: Path, dst: Path):
    ensure_dir(dst.parent)
    shutil.copy2(src, dst)

def up_to_date_in_any(paths: List[Path], remote_size: Optional[int], remote_updated_at: Optional[datetime]) -> Optional[Path]:
    for p in paths:
        if files_equal_by_size_and_date(p, remote_size, remote_updated_at):
            return p
    return None


# =================
# PROCESSAMENTO
# =================

def process_release_assets(release: dict, version_folder_name: str, subfolder_name: Optional[str] = None, force: bool = False):
    """Verifica/baixa/replica os assets da release diretamente nos DESTINATION_BASE_DIRS."""
    assets = release.get("assets") or []
    if not assets:
        print("Nenhum asset publicado nesta release.")
        return

    # Filtra apenas os diretórios de destino acessíveis
    accessible_dirs = []
    for base in DESTINATION_BASE_DIRS:
        # Normaliza o caminho antes de criar o Path
        normalized_base = normalize_unc_path(base)
        base_path = Path(normalized_base)
        if is_network_path_accessible(base_path):
            accessible_dirs.append(base_path)
            print(f"✅ Diretório acessível: {normalized_base}")
        else:
            print(f"❌ Diretório inacessível: {normalized_base}")
    
    if not accessible_dirs:
        print("⚠️ Nenhum diretório de destino está acessível.")
        print("   Verifique as credenciais de rede e conectividade.")
        return

    for asset in assets:
        name = sanitize_filename(asset.get("name") or "asset.bin")
        url = asset.get("browser_download_url")
        remote_size = asset.get("size")
        remote_updated_at = parse_github_ts(asset.get("updated_at"))

        if not url:
            print(f"- {name}: asset sem URL de download; pulando.")
            continue

        # Calcula destinos apenas para diretórios acessíveis
        dest_paths: List[Path] = []
        for base in accessible_dirs:
            version_dir = base / version_folder_name
            try:
                ensure_dir(version_dir)
                if subfolder_name:
                    version_dir = version_dir / subfolder_name
                    ensure_dir(version_dir)
                dest_paths.append(version_dir / name)
            except Exception as e:
                print(f"⚠️ Erro ao preparar destino {base}: {e}")
                continue

        if not dest_paths:
            print(f"⚠️ Nenhum destino válido para {name}; pulando.")
            continue

        if force:
            tmp = http_download_to_temp(url, remote_updated_at, name)
            try:
                for dp in dest_paths:
                    copy2_preserve(tmp, dp)
                print(f"• {name}: rebaixado e sobrescrito em {len(dest_paths)} destino(s).")
            finally:
                tmp.unlink(missing_ok=True)
            continue

        # Verifica se todos destinos já estão em dia
        all_ok = all(files_equal_by_size_and_date(p, remote_size, remote_updated_at) for p in dest_paths)
        if all_ok:
            print(f"• {name}: já atualizado em todos os destinos.")
            continue

        # Se algum destino está OK, replica dele para os demais
        source_ok = up_to_date_in_any(dest_paths, remote_size, remote_updated_at)
        if source_ok:
            for dp in dest_paths:
                if dp == source_ok:
                    continue
                if not files_equal_by_size_and_date(dp, remote_size, remote_updated_at):
                    copy2_preserve(source_ok, dp)
            print(f"• {name}: replicado de um destino existente para os demais.")
            continue

        # Nenhum destino está OK → baixa uma vez e distribui
        tmp = http_download_to_temp(url, remote_updated_at, name)
        try:
            if remote_size is not None and tmp.stat().st_size != remote_size:
                print(f"- {name}: tamanho do temporário difere do remoto; rebaixando...")
                tmp.unlink(missing_ok=True)
                tmp = http_download_to_temp(url, remote_updated_at, name)
            for dp in dest_paths:
                copy2_preserve(tmp, dp)
            print(f"• {name}: baixado uma vez e copiado para {len(dest_paths)} destino(s).")
        finally:
            tmp.unlink(missing_ok=True)


# ============
# CLI / MAIN
# ============

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Baixa/verifica Initial Release e Latest do Qlik Sense Desktop (sem cache/log).")
    p.add_argument("--initial-only", action="store_true", help="Processa apenas a Initial Release (padrão é Initial + Latest).")
    p.add_argument("--force", action="store_true", help="Rebaixa e sobrescreve todos os destinos.")
    return p.parse_args()

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
    Verifica se um caminho de rede é acessível sem tentar criar diretórios.
    
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
        
        # Tenta apenas verificar se o caminho existe ou pode ser acessado
        if path.exists():
            return True
        
        # Se não existe, tenta verificar o diretório pai
        parent = path.parent
        if parent.exists():
            return True
            
        # Para caminhos UNC, tenta verificar se o servidor responde
        path_str = str(path)
        if path_str.startswith("\\\\"):
            # Tenta listar o diretório pai para verificar conectividade
            try:
                parent_str = str(parent)
                if os.path.exists(parent_str):
                    return True
            except OSError:
                pass
                
        return False
        
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

def main():
    print_header()

    args = parse_args()

    # Configura credenciais de rede se disponíveis
    if NETWORK_USERNAME and NETWORK_PASSWORD:
        print("🔐 Configurando credenciais de rede...")
        setup_network_credentials()
    else:
        print("ℹ️ Credenciais de rede não configuradas.")

    # 1) Latest
    latest = get_latest_release()
    latest_name = (latest.get("name") or "").strip()
    if not latest_name:
        print("Não foi possível determinar o nome da última release.")
        sys.exit(1)
    print(f"Última release: {latest_name}")

    # 2) Ciclo (ex.: 'May 2025')
    cycle = extract_cycle_from_name(latest_name)
    if not cycle:
        print(f"Não foi possível extrair o ciclo (Mês Ano) de: {latest_name}")
        sys.exit(2)
    print(f"Ciclo detectado: {cycle}")

    # 3) Initial Release correspondente
    all_rels = get_all_releases(per_page=80)
    initial = find_initial_release_for_cycle(all_releases=all_rels, cycle=cycle)
    if not initial:
        print(f"Initial Release do ciclo '{cycle}' não encontrada.")
        sys.exit(3)
    initial_name = (initial.get("name") or "").strip()
    print(f"Initial Release: {initial_name}")

    # 4) Pasta de versão (nome da Latest)
    version_folder_name = sanitize_filename(latest_name)

    # 5) Processar Initial (sempre)
    print("Processando assets da Initial Release...")
    process_release_assets(initial, version_folder_name, subfolder_name="Initial Release", force=args.force)

    # 6) Processar Latest (por padrão SIM; só pula se --initial-only)
    if not args.initial_only:
        print("Processando assets da Latest...")
        process_release_assets(latest, version_folder_name, subfolder_name="Latest", force=args.force)

    print("Concluído.")

if __name__ == "__main__":
    main()
