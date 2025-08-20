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

def run_reports_pysql_homicidios():
    print(f"[{datetime.now()}] Gerando relatório de homicídios (pysql/pysql_homicidios.py)...")
    subprocess.run([python_exec, "pysql/pysql_homicidios.py"]) 

def run_statusqlik_desktop():
    print(f"[{datetime.now()}] Executando crawler_qlik/status_qlik_desktop.py...")
    subprocess.run([python_exec, "-m", "crawler_qlik.status_qlik_desktop"]) 

def run_statusqlik_etl():
    print(f"[{datetime.now()}] Executando crawler_qlik/status_qlik_etl.py...")
    subprocess.run([python_exec, "-m", "crawler_qlik.status_qlik_etl"]) 

# Agendamento
schedule.every().hour.at(":00").do(run_statusqlik_qmc)
schedule.every().day.at("05:00").do(run_reports_pysql_homicidios)
schedule.every().day.at("06:00").do(run_statusqlik_desktop)
schedule.every().day.at("07:00").do(run_statusqlik_etl)
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
    next_report = get_next_run_time("run_reports_pysql_homicidios")
    next_desktop = get_next_run_time("run_statusqlik_desktop")
    next_etl = get_next_run_time("run_statusqlik_etl")
    next_envio = get_next_run_time("run_send_statusqlik_evolution")
    print(f"Agora: {now} | Próx status/QMC: {next_status} | Próx relatório (05:00): {next_report} | Próx desktop (06:00): {next_desktop} | Próx ETL (07:00): {next_etl} | Próx envio (08:00): {next_envio}")
    schedule.run_pending()
    time.sleep(30)