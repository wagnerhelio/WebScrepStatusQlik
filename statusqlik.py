import os
import time
import csv
from datetime import datetime, date
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from colorama import init, Fore, Style

init(autoreset=True)
load_dotenv()

usuario = os.getenv("QLIK_USUARIO").encode().decode("unicode_escape")
senha = os.getenv("QLIK_SENHA")
CAMINHO_CHROMEDRIVER = os.getenv("CHROMEDRIVER")

QMCs = [
    {"nome": "estatistica", "url_login": os.getenv("QLIK_QMC1"), "url_tasks": os.getenv("QLIK_TASK1")},
    {"nome": "paineis", "url_login": os.getenv("QLIK_QMC2"), "url_tasks": os.getenv("QLIK_TASK2")}
]

status_map = {
    "icon-qmc-task-finishedsuccess": "Success",
    "icon-qmc-task-finishedfail": "Failed",
    "icon-qmc-task-finishedqueued": "Queued",
    "icon-qmc-task-finishedneverstarted": "Never started",
    "icon-qmc-task-finishedstarted": "Started",
    "icon-qmc-task-finishedtriggered": "Triggered",
    "icon-qmc-task-abort-initiated": "Abort initiated",
    "icon-qmc-task-aborting": "Aborting",
    "icon-qmc-task-finishedaborted": "Aborted",
    "icon-qmc-task-finishedskipped": "Skipped",
    "icon-qmc-task-finishedretrying": "Retrying",
    "icon-qmc-task-finishederror": "Error",
    "icon-qmc-task-finishedreset": "Reset"
}

cores = {
    "Success": Fore.GREEN,
    "Em rota de atualização": Fore.BLUE,
    "Failed": Fore.RED,
    "Error": Fore.RED,
    "Outros": Fore.YELLOW,
}

def colorir(status, texto):
    return cores.get(status, Fore.YELLOW) + texto + Style.RESET_ALL

def esperar_popover_abrir(icone, max_tentativas=10):
    for i in range(max_tentativas):
        try:
            icone.click()
            print(f"🖱️ Clique {i+1} no ícone. Aguardando data-ongoing='true'...")
            time.sleep(1.5)
            if icone.get_attribute("data-ongoing") == "true":
                return True
        except Exception as e:
            print(f"⚠️ Erro ao clicar no ícone: {e}")
        time.sleep(1)
    return False

def coletar_status(nome_sufixo, url_login, url_tasks):
    print(f"\n🌐 Iniciando sessão em: {url_login}")

    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_argument("--incognito")
    options.add_experimental_option("prefs", {
        "download.default_directory": os.path.abspath("logs_qmc")
    })
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
            try:
                colunas = linha.find_elements(By.TAG_NAME, "td")
                if len(colunas) < 7:
                    continue

                nome = colunas[0].text.strip()
                ultima_execucao = colunas[5].text.strip()

                icone_status = colunas[4].find_element(By.CSS_SELECTOR, "i[class^='icon-qmc-task']")
                classe_status = next((cls for cls in icone_status.get_attribute("class").split() if cls.startswith("icon-qmc-task")), "")
                status = status_map.get(classe_status, "Outros")

                if status == "Success":
                    try:
                        data_execucao = datetime.strptime(ultima_execucao[:16], "%Y-%m-%d %H:%M").date()
                        if data_execucao != hoje:
                            status = "Em rota de atualização"
                    except:
                        status = "Em rota de atualização"

                tarefas_por_status.setdefault(status, []).append([nome, status, ultima_execucao])

                # Baixar log se Failed
                if status == "Failed":
                    print(f"\n⚠️ Tentando baixar log da tarefa '{nome}'...")
                    driver.execute_script("arguments[0].scrollIntoView({behavior: 'auto', block: 'center'});", linha)
                    time.sleep(0.5)
                    icone_info = colunas[4].find_element(By.CSS_SELECTOR, "i.icon-qmc-info")
                    if esperar_popover_abrir(icone_info):
                        print(f"✅ Popover aberto para '{nome}'. Procurando botão de download...")
                        botao_log = WebDriverWait(driver, 10).until(
                            EC.element_to_be_clickable((By.XPATH, "//div[text()='Download script log']"))
                        )
                        botao_log.click()
                        print(f"📥 Log da tarefa '{nome}' baixado com sucesso.")
                        time.sleep(2)
                        
                        # Renomeia o último .tmp baixado para o nome da tarefa
                        download_dir = os.path.abspath("logs_qmc")
                        arquivos_tmp = [f for f in os.listdir(download_dir) if f.endswith(".tmp")]
                        if arquivos_tmp:
                            mais_recente = max(arquivos_tmp, key=lambda x: os.path.getctime(os.path.join(download_dir, x)))
                            caminho_antigo = os.path.join(download_dir, mais_recente)
                            caminho_novo = os.path.join(download_dir, f"{nome}.log")
                            os.rename(caminho_antigo, caminho_novo)
                            print(f"📄 Log renomeado para: {caminho_novo}")
                            try:
                                os.remove(caminho_antigo)
                                print(f"🧹 Arquivo temporário removido: {caminho_antigo}")
                            except Exception as e:
                                print(f"⚠️ Erro ao remover .tmp: {e}")
                        else:
                            print("⚠️ Nenhum arquivo .tmp encontrado para renomear.")
                    else:
                        print(f"⏱️ Timeout: popover não abriu para '{nome}'")
            except Exception as e:
                print(f"⚠️ Erro ao processar linha: {e}")

            
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

# Garante que pasta existe
os.makedirs("logs_qmc", exist_ok=True)

# Executa
for qmc in QMCs:
    coletar_status(qmc["nome"], qmc["url_login"], qmc["url_tasks"])
