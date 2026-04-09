#!/usr/bin/env python3
"""
Teste rápido: envia uma mensagem de texto apenas ao grupo de controle
(EVO_GRUPO_CONTROLE ou, em legado, EVO_GRUPO_ADMIN). Não envia ao grupo oficial.
Inclui hostname e IPs da máquina.
"""
from __future__ import annotations

import os
import platform
import socket
import subprocess
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)


def _local_ipv4_summary() -> str:
    if os.name == "nt":
        try:
            out = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    "(Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue | "
                    "Where-Object { $_.IPAddress -notlike '169.254.*' }).IPAddress -join ', '",
                ],
                capture_output=True,
                text=True,
                timeout=15,
                encoding="utf-8",
                errors="replace",
            )
            s = (out.stdout or "").strip()
            if s:
                return s
        except Exception:
            pass
    try:
        hn = socket.gethostname()
        _, _, ips = socket.gethostbyname_ex(hn)
        return ", ".join(ip for ip in ips if not ip.startswith("127.")) or ", ".join(ips) or "(sem IPv4)"
    except Exception:
        return "(IPs indisponiveis)"


def _mensagem_teste() -> str:
    host = socket.gethostname()
    try:
        fqdn = socket.getfqdn()
    except Exception:
        fqdn = host
    ips = _local_ipv4_summary()
    sistema = f"{platform.system()} {platform.release()}"
    return (
        "*Teste PySQL + Evolution*\n\n"
        "OK - funcionando.\n\n"
        f"Maquina: `{host}`\n"
        f"FQDN: `{fqdn}`\n"
        f"IPs (IPv4): {ips}\n"
        f"SO: {sistema}\n"
    )


def main() -> int:
    os.chdir(PROJECT_ROOT)
    if os.name == "nt":
        try:
            os.system("chcp 65001 > nul")
            if hasattr(sys.stdout, "reconfigure"):
                sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    from evolution_api.send_pysql_evolution import (
        destinos_controle,
        enviar_para_destinos_controle,
        enviar_mensagem_texto,
    )

    alvos = destinos_controle()
    if not alvos:
        print(
            "ERRO: Nenhum grupo de controle configurado.\n"
            "Defina EVO_GRUPO_CONTROLE ou EVO_GRUPO_ADMIN no .env (JID do grupo, ex.: ...@g.us).",
            file=sys.stderr,
        )
        return 1

    print(f"Enviando teste apenas para grupo(s) de controle ({len(alvos)}):", flush=True)
    for j in alvos:
        print(f"  - {j}", flush=True)

    msg = _mensagem_teste()
    stats = enviar_para_destinos_controle(enviar_mensagem_texto, msg)
    ok = stats.get("sucessos", 0) > 0
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
