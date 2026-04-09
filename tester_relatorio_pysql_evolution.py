#!/usr/bin/env python3
"""
Teste de relatorios PySQL: executa os scripts, envia resumos, PDFs/XLSX e logs
apenas para o grupo de controle (EVO_GRUPO_CONTROLE / EVO_GRUPO_ADMIN).
Nao envia ao grupo oficial nem a EVO_DESTINO / EVO_GRUPO_OFICIAL.
"""
from __future__ import annotations

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

PREFIXO_TESTE = "[TESTE - relatorio PySQL]\n\n"


def main() -> int:
    os.chdir(PROJECT_ROOT)
    if os.name == "nt":
        try:
            os.system("chcp 65001 > nul")
            if hasattr(sys.stdout, "reconfigure"):
                sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    import evolution_api.send_pysql_evolution as sp

    if not sp.destinos_controle():
        print(
            "ERRO: Nenhum grupo de controle configurado.\n"
            "Defina EVO_GRUPO_CONTROLE ou EVO_GRUPO_ADMIN no .env.",
            file=sys.stderr,
        )
        return 1

    def enviar_texto_com_prefixo(dest: str, texto: str) -> bool:
        t = texto if texto.strip().startswith("[TESTE") else PREFIXO_TESTE + texto
        return sp.enviar_mensagem_texto(dest, t)

    def enviador_controle_prefixado(func_envio, texto: str):
        return sp.enviar_para_destinos_controle(enviar_texto_com_prefixo, texto)

    print("=" * 60, flush=True)
    print("TESTE: relatorios PySQL — somente grupo de controle", flush=True)
    print("=" * 60, flush=True)

    sp.verificar_dependencias_pysql()

    print("\n" + "=" * 60, flush=True)
    print("Execucao dos scripts PySQL", flush=True)
    print("=" * 60, flush=True)
    try:
        _, scripts_falharam = sp.executar_scripts_pysql()
    except KeyboardInterrupt:
        print("Interrompido.", flush=True)
        return 130

    if scripts_falharam:
        aviso = (
            PREFIXO_TESTE
            + "Scripts com falha nesta rodada de teste:\n"
            + "\n".join(f"- {s}" for s in scripts_falharam)
        )
        sp.enviar_para_destinos_controle(sp.enviar_mensagem_texto, aviso)

    print("\n" + "=" * 60, flush=True)
    print("Envio de resumos de tempo (controle)", flush=True)
    print("=" * 60, flush=True)
    try:
        sp.enviar_resumos_tempo(enviador_texto=enviador_controle_prefixado)
    except Exception as e:
        print(f"Aviso resumos: {e}", flush=True)

    print("\n" + "=" * 60, flush=True)
    print("Envio de PDFs e auditorias RAIs (controle)", flush=True)
    print("=" * 60, flush=True)
    try:
        sp.enviar_pdfs_e_auditorias_rais(
            enviador_texto=enviador_controle_prefixado,
            enviador_arquivo=sp.enviar_para_destinos_controle,
        )
    except Exception as e:
        print(f"Aviso PDFs: {e}", flush=True)

    print("\n" + "=" * 60, flush=True)
    print("Envio de logs de erro (controle)", flush=True)
    print("=" * 60, flush=True)
    try:
        sp.enviar_logs_erro(
            enviador_texto=enviador_controle_prefixado,
            enviador_arquivo=sp.enviar_para_destinos_controle,
        )
    except Exception as e:
        print(f"Aviso logs: {e}", flush=True)

    print("\nTeste concluido. Nada foi enviado ao grupo oficial.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
