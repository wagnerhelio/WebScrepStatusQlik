#!/usr/bin/env python3
"""
Scheduler exclusivo: PySQL + Evolution API

Dispara apenas a rotina de relatórios PySQL (homicídios e feminicídios) e o envio
via Evolution API. Não executa Status Qlik nem Envio Qlik.

Comportamento:
  - Envio 1x por dia. Histórico em pysql/historico_pysql_evolution.json.
  - Horário preferido: PYSQL_SCHEDULER_HORA:MINUTO (padrão 08:00).
  - Se o scheduler for iniciado após o horário e ainda não tiver enviado hoje,
    dispara na próxima verificação (cumprindo 1x/dia mesmo fora do horário).
  - Se já enviou hoje, aguarda o próximo dia.

Uso:
  python scheduler_pysql_evolution.py

  Para orquestração completa (venv + ExecutionPolicy + Docker + registro webhook + scheduler), use:
  .\\iniciar_pysql_evolution.ps1   ou   iniciar_pysql_evolution.bat

Variáveis de ambiente (opcional, no .env da raiz):
  PYSQL_SCHEDULER_HORA   - Hora do dia para disparo (0-23). Padrão: 8
  PYSQL_SCHEDULER_MINUTO - Minuto (0-59). Padrão: 0
  PYSQL_SCHEDULER_INTERVALO_SEG - Intervalo de verificação em segundos. Padrão: 60
"""

import os
import sys
import time
import subprocess
import queue
from datetime import datetime
from pathlib import Path
from threading import Thread

# UTF-8 no Windows
if os.name == "nt":
    try:
        os.system("chcp 65001 > nul")
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

# Carrega .env da raiz para PYSQL_SCHEDULER_*
try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")
except Exception:
    pass

HORA_PADRAO = int(os.getenv("PYSQL_SCHEDULER_HORA", "8"))
MINUTO_PADRAO = int(os.getenv("PYSQL_SCHEDULER_MINUTO", "0"))
INTERVALO_VERIFICACAO = int(os.getenv("PYSQL_SCHEDULER_INTERVALO_SEG", "60"))
WEBHOOK_PYSQL_ENABLED = os.getenv("WEBHOOK_PYSQL_ENABLED", "true").strip().lower() in ("1", "true", "yes")
WEBHOOK_PYSQL_PORT = os.getenv("WEBHOOK_PYSQL_PORT", "5050").strip()
EVOLUTION_BOT_NUMBER = (os.getenv("EVOLUTION_BOT_NUMBER") or "").strip().replace(" ", "")


def _validar_webhook():
    """Valida configuração do webhook; retorna (ok: bool, mensagem: str)."""
    if not WEBHOOK_PYSQL_ENABLED:
        return True, "desativado (WEBHOOK_PYSQL_ENABLED=false)"
    try:
        import flask  # noqa: F401
    except ImportError:
        return False, "Flask não instalado. Execute: pip install flask"
    if not EVOLUTION_BOT_NUMBER or not EVOLUTION_BOT_NUMBER.isdigit():
        return False, "EVOLUTION_BOT_NUMBER não definido ou inválido no .env (use só dígitos, ex.: 5562995071258)"
    if len(EVOLUTION_BOT_NUMBER) < 10:
        return False, "EVOLUTION_BOT_NUMBER deve ter pelo menos 10 dígitos (DDI + DDD + número)"
    return True, "ok"


def _iniciar_webhook_em_thread():
    """Inicia o servidor webhook em thread para comando por WhatsApp (@robô)."""
    ok, msg = _validar_webhook()
    if not ok:
        print(f"   Webhook PySQL: não iniciado ({msg})", flush=True)
        return None
    if msg != "ok":
        print(f"   Webhook PySQL: {msg}", flush=True)
        return None
    try:
        import evolution_api.webhook_pysql as webhook_mod
        webhook_mod.RELATORIO_PEDIDO_QUEUE = queue.Queue()
        from evolution_api.webhook_pysql import run_webhook_server
        th = Thread(target=run_webhook_server, daemon=True)
        th.start()
        time.sleep(0.5)
        print("   Webhook PySQL: ativo (comando por @ no WhatsApp)", flush=True)
        print(f"   URL para registrar na Evolution: http://<SEU_IP>:{WEBHOOK_PYSQL_PORT}/webhook", flush=True)
        return webhook_mod.RELATORIO_PEDIDO_QUEUE
    except Exception as e:
        print(f"   Webhook PySQL: não iniciado ({e})", flush=True)
        return None


def executar_tarefa(script_path: str, descricao: str, timeout_seg: int = 10800) -> bool:
    """
    Executa um script Python com retry (até 3 tentativas).
    timeout_seg: 3h por padrão para os relatórios PySQL.
    """
    for tentativa in range(3):
        try:
            print(f"   Executando {descricao} (tentativa {tentativa + 1}/3)...", flush=True)
            notificar_controle = tentativa == 2
            result = subprocess.run(
                [sys.executable, "-u", str(script_path)],
                cwd=PROJECT_ROOT,
                env={
                    **os.environ,
                    "PYTHONIOENCODING": "utf-8",
                    "PYTHONUTF8": "1",
                    "PYSQL_RETRY_ATTEMPT": str(tentativa + 1),
                    "PYSQL_RETRY_MAX": "3",
                    "PYSQL_NOTIFY_CONTROL_ON_FAILURE": "true" if notificar_controle else "false",
                },
                capture_output=False,
                timeout=timeout_seg,
            )
            if result.returncode == 0:
                print(f"   OK {descricao}", flush=True)
                return True
            if tentativa < 2:
                print(
                    f"   Falhou {descricao} (código {result.returncode}) "
                    f"- nova tentativa {tentativa + 2}/3. "
                    f"Notificação de controle suprimida nesta tentativa.",
                    flush=True,
                )
            else:
                print(
                    f"   Falhou {descricao} (código {result.returncode}) "
                    f"- última tentativa do ciclo; notificação ao controle liberada.",
                    flush=True,
                )
        except subprocess.TimeoutExpired:
            print(f"   Timeout {descricao}", flush=True)
        except KeyboardInterrupt:
            print(f"   Interrompido pelo usuário", flush=True)
            return False
        except Exception as e:
            print(f"   Erro {descricao}: {e}", flush=True)
    return False


def rodar_pysql_evolution():
    """Dispara o módulo send_pysql_evolution (executa scripts PySQL + envia via Evolution)."""
    script = PROJECT_ROOT / "evolution_api" / "send_pysql_evolution.py"
    if not script.exists():
        print(f"   Script não encontrado: {script}", flush=True)
        return False
    return executar_tarefa(
        script,
        "PySQL + Envio Evolution API",
        timeout_seg=10800,  # 3 horas
    )


def rodar_pysql_evolution_para_jid(remote_jid: str):
    """Executa send_pysql_evolution com --enviar-para (pedido pelo webhook). Saída no console."""
    script = PROJECT_ROOT / "evolution_api" / "send_pysql_evolution.py"
    if not script.exists():
        print(f"   Script não encontrado: {script}", flush=True)
        return False
    print(f"\n[webhook] Executando relatório PySQL sob demanda (destino: {remote_jid})", flush=True)
    print("=" * 60, flush=True)
    try:
        result = subprocess.run(
            [sys.executable, "-u", str(script), "--enviar-para", remote_jid],
            cwd=PROJECT_ROOT,
            env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1", "PYTHONUNBUFFERED": "1"},
            capture_output=False,
            timeout=10800,
        )
        if result.returncode == 0:
            print("=" * 60, flush=True)
            print("[webhook] Relatório PySQL concluído com sucesso.", flush=True)
            return True
        print("=" * 60, flush=True)
        print(f"[webhook] Relatório PySQL falhou (código {result.returncode}).", flush=True)
        try:
            from evolution_api.send_pysql_evolution import enviar_mensagem_texto
            from evolution_api.webhook_pysql import MSG_ERRO
            enviar_mensagem_texto(remote_jid, MSG_ERRO + f" (código {result.returncode})")
        except Exception:
            pass
        return False
    except subprocess.TimeoutExpired:
        print("[webhook] Relatório PySQL: timeout.", flush=True)
        try:
            from evolution_api.send_pysql_evolution import enviar_mensagem_texto
            from evolution_api.webhook_pysql import MSG_ERRO
            enviar_mensagem_texto(remote_jid, MSG_ERRO + " (timeout)")
        except Exception:
            pass
        return False
    except Exception as e:
        print(f"[webhook] Erro ao executar relatório: {e}", flush=True)
        try:
            from evolution_api.send_pysql_evolution import enviar_mensagem_texto
            from evolution_api.webhook_pysql import MSG_ERRO
            enviar_mensagem_texto(remote_jid, MSG_ERRO + f" ({str(e)[:80]})")
        except Exception:
            pass
        return False


def main():
    from pysql.historico_pysql_evolution import (
        data_ultimo_envio_sucesso,
        registrar_envio,
        ler_e_limpar_resumo_falha,
    )

    print("=" * 60, flush=True)
    print("Scheduler PySQL + Evolution API", flush=True)
    print("=" * 60, flush=True)
    print(f"   Disparo diário: 1x por dia (preferência {HORA_PADRAO:02d}:{MINUTO_PADRAO:02d})", flush=True)
    print(f"   Se hoje ainda não enviou e já passou do horário → dispara na próxima verificação.", flush=True)
    print(f"   Histórico: pysql/historico_pysql_evolution.json", flush=True)
    print(f"   Verificação a cada {INTERVALO_VERIFICACAO}s | Ctrl+C para encerrar", flush=True)
    relatorio_queue = _iniciar_webhook_em_thread()
    print("=" * 60, flush=True)

    try:
        while True:
            # Pedidos de relatório pelo WhatsApp (executados no thread principal para logs no console)
            if relatorio_queue is not None:
                try:
                    while not relatorio_queue.empty():
                        jid = relatorio_queue.get_nowait()
                        rodar_pysql_evolution_para_jid(jid)
                except queue.Empty:
                    pass
                except Exception as e:
                    print(f"[webhook] Erro ao processar fila de relatório: {e}", flush=True)

            agora = datetime.now()
            hoje = agora.date().isoformat()
            ultima_data_envio = data_ultimo_envio_sucesso()

            # Deve rodar se ainda não enviou hoje
            ja_enviou_hoje = ultima_data_envio == hoje
            horario_passou = (agora.hour, agora.minute) >= (HORA_PADRAO, MINUTO_PADRAO)

            if not ja_enviou_hoje and horario_passou:
                print(f"\n[{agora.strftime('%Y-%m-%d %H:%M:%S')}] Disparo: PySQL + Evolution (1x/dia)", flush=True)
                sucesso = rodar_pysql_evolution()
                resumo_falha = ler_e_limpar_resumo_falha() if not sucesso else None
                registrar_envio(sucesso, agora, resumo_falha=resumo_falha)
                if sucesso:
                    print(f"   Concluído. Próximo envio: amanhã.", flush=True)
                else:
                    print(f"   Falha no fluxo PySQL/Evolution. Nova tentativa no próximo ciclo.", flush=True)

            time.sleep(INTERVALO_VERIFICACAO)

    except KeyboardInterrupt:
        print("\nScheduler encerrado.", flush=True)


if __name__ == "__main__":
    main()
