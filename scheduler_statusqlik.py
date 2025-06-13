import schedule
import time
import subprocess
from datetime import datetime
import sys

def log(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")

# Use o interpretador da venv
python_exec = sys.executable

# Tarefas programadas
def executar_status_qmc():
    log("Executando: statusqlik_qmc.py")
    subprocess.run([python_exec, "statusqlik_qmc.py"])

def executar_status_nprinting():
    log("Executando: statusqlik_nprinting.py")
    subprocess.run([python_exec, "statusqlik_nprinting.py"])

def executar_envio_evolution():
    log("Executando: send_statusqlik_evolution.py")
    subprocess.run([python_exec, "send_statusqlik_evolution.py"])

# Agenda diária
schedule.every().day.at("12:02").do(executar_status_qmc)
schedule.every().day.at("12:03").do(executar_status_nprinting)
schedule.every().day.at("12:04").do(executar_envio_evolution)

log("⏰ Agendador iniciado. Aguardando tarefas...")

# Loop infinito
while True:
    schedule.run_pending()
    time.sleep(30)
