import schedule
import time
import subprocess
from datetime import datetime, timedelta
import sys
import os
import glob

python_exec = sys.executable

def limpar_pasta_mais_recente(pasta, extensoes=(".pdf", ".txt")):
    arquivos = [os.path.join(pasta, f) for f in os.listdir(pasta) if os.path.isfile(os.path.join(pasta, f)) and f.endswith(extensoes)]
    if not arquivos:
        return
    grupos = {}
    for arq in arquivos:
        nome = os.path.basename(arq)
        partes = nome.split("_")
        if len(partes) < 4:
            continue
        sufixo = partes[2]
        ext = os.path.splitext(nome)[1]
        grupos.setdefault((sufixo, ext), []).append(arq)
    for (sufixo, ext), lista in grupos.items():
        lista.sort(key=os.path.getctime, reverse=True)
        for arq in lista[1:]:
            try:
                os.remove(arq)
            except Exception as e:
                print(f"Erro ao remover {arq}: {e}")

def limpar_errorlogs(pasta):
    arquivos = [os.path.join(pasta, f) for f in os.listdir(pasta) if os.path.isfile(os.path.join(pasta, f))]
    if not arquivos:
        return
    grupos = {}
    for arq in arquivos:
        nome = os.path.basename(arq)
        base = nome.split(".")[0]
        grupos.setdefault(base, []).append(arq)
    for base, lista in grupos.items():
        lista.sort(key=os.path.getctime, reverse=True)
        for arq in lista[1:]:
            try:
                os.remove(arq)
            except Exception as e:
                print(f"Erro ao remover {arq}: {e}")

def run_statusqlik_qmc():
    print(f"[{datetime.now()}] Executando statusqlik_qmc.py...")
    subprocess.run([python_exec, "statusqlik_qmc.py"])

def run_statusqlik_nprinting():
    print(f"[{datetime.now()}] Executando statusqlik_nprinting.py...")
    subprocess.run([python_exec, "statusqlik_nprinting.py"])

def run_send_statusqlik_evolution():
    print(f"[{datetime.now()}] Enviando resumo e arquivos...")
    subprocess.run([python_exec, "send_statusqlik_evolution.py"])
    limpar_pasta_mais_recente("tasks_qmc")
    limpar_pasta_mais_recente("tasks_nprinting")
    limpar_errorlogs("errorlogs")
    limpar_errorlogs("errorlogs_nprinting")

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