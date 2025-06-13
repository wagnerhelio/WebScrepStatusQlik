import schedule
import time
import subprocess
from datetime import datetime

def log(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")

# Tarefas programadas
def executar_status_qmc():
    log("Executando: statusqlik_qmc.py")
    subprocess.run(["python", "statusqlik_qmc.py"])

def executar_status_nprinting():
    log("Executando: statusqlik_nprinting.py")
    subprocess.run(["python", "statusqlik_nprinting.py"])

def executar_envio_evolution():
    log("Executando: send_statusqlik_evolution.py")
    subprocess.run(["python", "send_statusqlik_evolution.py"])

# Agenda diária
schedule.every().day.at("07:45").do(executar_status_qmc)
schedule.every().day.at("07:50").do(executar_status_nprinting)
schedule.every().day.at("08:00").do(executar_envio_evolution)

log("⏰ Agendador iniciado. Aguardando tarefas...")

# Loop infinito
while True:
    schedule.run_pending()
    time.sleep(30)  # Verifica a cada 30 segundos
