import schedule
import time
import subprocess
from datetime import datetime, timedelta
import sys
import os
import glob

python_exec = sys.executable

# (Funções limpar_pasta_mais_recente e limpar_errorlogs removidas)

def run_statusqlik_qmc():
    print(f"[{datetime.now()}] Executando crawler_qlik/status_qlik_task.py...")
    subprocess.run([python_exec, "-m", "crawler_qlik.status_qlik_task"]) 

def run_statusqlik_nprinting():
    print(f"[{datetime.now()}] Executando crawler_qlik/status_qlik_task.py (NPrinting e QMC)...")
    subprocess.run([python_exec, "-m", "crawler_qlik.status_qlik_task"]) 

def run_send_statusqlik_evolution():
    print(f"[{datetime.now()}] Enviando resumo e arquivos...")
    # Limpa as pastas ANTES do envio, mantendo só o mais recente de cada tipo
    # (Funções limpar_pasta_mais_recente e limpar_errorlogs removidas)
    subprocess.run([python_exec, "-m", "evolution_api.send_evolution"]) 

# Agendamento
schedule.every().hour.at(":00").do(run_statusqlik_qmc)
schedule.every().day.at("08:00").do(run_send_statusqlik_evolution)

print("Agendador iniciado. Pressione Ctrl+C para sair.")

def get_next_run_time(job_func_name):
    jobs = [job for job in schedule.get_jobs() if getattr(job.job_func, "__name__", str(job.job_func)) == job_func_name]
    if jobs and jobs[0].next_run is not None:
        return jobs[0].next_run.strftime("%H:%M:%S")
    return "-"

while True:
    now = datetime.now().strftime("%H:%M:%S")
    next_status = get_next_run_time("run_statusqlik_qmc")
    next_envio = get_next_run_time("run_send_statusqlik_evolution")
    print(f"Agora: {now} | Próxima checagem de status: {next_status} | Próximo envio de resumo: {next_envio}")
    schedule.run_pending()
    time.sleep(30)