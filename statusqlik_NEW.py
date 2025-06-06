import os
import time
import csv
from datetime import datetime, date
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.keys import Keys
from colorama import init, Fore, Style

init(autoreset=True)  # Habilita reset automático de cor

# Carrega variáveis do .env
load_dotenv()
usuario = os.getenv("QLIK_USUARIO").encode().decode("unicode_escape")
senha = os.getenv("QLIK_SENHA")
CAMINHO_CHROMEDRIVER = os.getenv("CHROMEDRIVER")

QMCs = [
    {"nome": "estatistica", "url_login": os.getenv("QLIK_QMC1"), "url_tasks": os.getenv("QLIK_TASK1")},
    {"nome": "paineis", "url_login": os.getenv("QLIK_QMC2"), "url_tasks": os.getenv("QLIK_TASK2")}
]

status_map = {
    "icon-qmc-task-finishedneverstarted": "Never started",
    "icon-qmc-task-finishedtriggered": "Triggered",
    "icon-qmc-task-finishedstarted": "Started",
    "icon-qmc-task-finishedqueued": "Queued",
    "icon-qmc-task-abort-initiated": "Abort initiated",
    "icon-qmc-task-aborting": "Aborting",
    "icon-qmc-task-finishedaborted": "Aborted",
    "icon-qmc-task-finishedsuccess": "Success",
    "icon-qmc-task-finishedfail": "Failed",
    "icon-qmc-task-finishedskipped": "Skipped",
    "icon-qmc-task-finishedretrying": "Retrying",
    "icon-qmc-task-finishederror": "Error",
    "icon-qmc-task-finishedreset": "Reset",
}

cores = {
    "Success": Fore.GREEN,
    "Em rota de atualização": Fore.BLUE,
    "Failed": Fore.RED,
    "Error": Fore.RED,
    "Outros": Fore.YELLOW,
}

def colorir(status, texto):
    cor = cores.get(status, Fore.YELLOW)
    return cor + texto + Style.RESET_ALL

def coletar_status(nome_sufixo, url_login, url_tasks):
    print(f"\n🌐 Iniciando sessão em: {url_login}")

    options = webdriver.ChromeOptions()
    driver = webdriver.Chrome(service=Service(CAMINHO_CHROMEDRIVER), options=options)

    try:
        driver.get(url_login)
        time.sleep(2)
        driver.find_element(By.ID, "username-input").send_keys(usuario)
        campo_senha = driver.find_element(By.ID, "password-input")
        campo_senha.send_keys(senha)
        campo_senha.send_keys(Keys.ENTER)
        print("✅ Login enviado.")
        time.sleep(5)

        driver.get(url_tasks)
        print("📄 Carregando tarefas...")
        time.sleep(6)

        linhas = driver.find_elements(By.CSS_SELECTOR, "table.qmc-table-rows tbody tr")
        hoje = date.today()
        tarefas_por_status = {}

        for linha in linhas:
            colunas = linha.find_elements(By.TAG_NAME, "td")
            if len(colunas) >= 7:
                nome = colunas[0].text.strip()
                ultima_execucao = colunas[5].text.strip()

                try:
                    icone = colunas[4].find_element(By.CSS_SELECTOR, "i[class^='icon-qmc-task']")
                    classe_status = next((cls for cls in icone.get_attribute("class").split() if cls.startswith("icon-qmc-task")), "")
                    status = status_map.get(classe_status, "Outros")
                except:
                    status = "Outros"

                if status == "Success":
                    try:
                        data_execucao = datetime.strptime(ultima_execucao[:16], "%Y-%m-%d %H:%M").date()
                        if data_execucao != hoje:
                            status = "Em rota de atualização"
                    except:
                        status = "Em rota de atualização"

                tarefas_por_status.setdefault(status, []).append([nome, status, ultima_execucao])

        print(f"\n📋 Tarefas no QMC '{nome_sufixo}':")
        for status, tarefas in sorted(tarefas_por_status.items()):
            print(colorir(status, f"\n🔸 Status: {status} ({len(tarefas)} tarefa(s))"))
            for nome, _, data in tarefas:
                print(f" - {nome} | Última Execução: {data}")

        print("\n📊 Resumo:")
        for status, tarefas in sorted(tarefas_por_status.items()):
            print(colorir(status, f" - {status}: {len(tarefas)}"))

        nome_arquivo = f"status_qlik_{nome_sufixo}_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.csv"
        with open(nome_arquivo, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Nome da Tarefa", "Status", "Última Execução"])
            for tarefas in tarefas_por_status.values():
                for registro in tarefas:
                    writer.writerow(registro)

        print(f"\n✅ Dados exportados para: {nome_arquivo}")
    finally:
        driver.quit()

for qmc in QMCs:
    coletar_status(qmc["nome"], qmc["url_login"], qmc["url_tasks"])
