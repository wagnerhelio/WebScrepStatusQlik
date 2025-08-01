import os
import time
import pandas as pd
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
from xhtml2pdf import pisa
from jinja2 import Environment, FileSystemLoader
from selenium.webdriver.remote.webelement import WebElement

init(autoreset=True)
load_dotenv()

usuario = os.getenv("QLIK_USUARIO").encode().decode("unicode_escape")
senha = os.getenv("QLIK_SENHA")
CAMINHO_CHROMEDRIVER = os.getenv("CHROMEDRIVER")

QMCs = [
    {"nome": "estatistica", "url_login": os.getenv("QLIK_QMC_QAP"), "url_tasks": os.getenv("QLIK_TASK_QAP")},
    {"nome": "paineis", "url_login": os.getenv("QLIK_QMC_HUB"), "url_tasks": os.getenv("QLIK_TASK_HUB")}
]

status_map = {
    "icon-qmc-task-finishedsuccess": "Success",
    "icon-qmc-task-finishedfail": "Failed",
    "icon-qmc-task-finishedqueued": "Queued",
    "icon-qmc-task-finishedneverstarted": "Never started",
    "icon-qmc-task-started": "Started",
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
        "download.default_directory": os.path.abspath("errorlogs"),
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
                    linha.click()

                    # Espera até que a linha fique com a classe "row row-selected"
                    def is_row_selected():
                        if isinstance(linha, WebElement):
                            class_attr = linha.get_attribute("class")
                            return class_attr is not None and "row-selected" in class_attr
                        return False
                    WebDriverWait(driver, 5).until(lambda d: is_row_selected())
                    print(f"✅ Linha '{nome}' marcada como selecionada.")
                    time.sleep(2)
                    # Clica no botão de log
                    icone_info = colunas[4].find_element(By.CSS_SELECTOR, "i.icon-qmc-info")
                    if esperar_popover_abrir(icone_info):
                        print(f"✅ Log aberto para '{nome}'. Procurando botão de download...")
                        botao_log = WebDriverWait(driver, 10).until(
                            EC.element_to_be_clickable((By.XPATH, "//div[text()='Download script log']"))
                        )
                        botao_log.click()
                        print(f"📥 Log da tarefa '{nome}' baixado com sucesso.")
                        time.sleep(5)
                        download_dir = os.path.abspath("errorlogs")

                        # Aguarda até 10s pelo novo arquivo .tmp
                        tmp_encontrado = None
                        for _ in range(10):
                            arquivos = [f for f in os.listdir(download_dir) if f.endswith(".tmp")]
                            if arquivos:
                                tmp_encontrado = max(arquivos, key=lambda f: os.path.getctime(os.path.join(download_dir, f)))
                                break
                            time.sleep(1)

                        if tmp_encontrado:
                            caminho_antigo = os.path.join(download_dir, tmp_encontrado)
                            caminho_novo = os.path.join(download_dir, f"{nome}.txt")
                            try:
                                os.rename(caminho_antigo, caminho_novo)
                                print(f"📄 Log renomeado para: {caminho_novo}")
                                # Clica no botão Start após garantir que está habilitado
                                try:
                                    WebDriverWait(driver, 10).until(
                                        lambda d: d.find_element(By.ID, "qmc.actionbar.task.start").find_element(By.TAG_NAME, "button").is_enabled()
                                    )
                                    start_button = driver.find_element(By.ID, "qmc.actionbar.task.start").find_element(By.TAG_NAME, "button")
                                    driver.execute_script("arguments[0].click();", start_button)
                                    time.sleep(5)
                                    print(f"▶️ Tarefa '{nome}' foi reiniciada com sucesso.")
                                except Exception as e:
                                    print(f"⚠️ Erro ao tentar clicar no botão Start da tarefa '{nome}': {e}")
                            except Exception as e:
                                print(f"⚠️ Erro ao renomear: {e}")
                        else:
                            print("⚠️ Nenhum arquivo .tmp encontrado para renomear.")
                    else:
                        print(f"⏱️ Timeout: Error log não abriu para '{nome}'")
            except Exception as e:
                print(f"⚠️ Erro ao tentar baixar o log '{nome}'")
                # Clica no botão Start após garantir que está habilitado
                try:
                    # Aguarda até o botão Start estar habilitado
                    WebDriverWait(driver, 10).until(
                        lambda d: d.find_element(By.ID, "qmc.actionbar.task.start").find_element(By.TAG_NAME, "button").is_enabled()
                    )
                    start_button = driver.find_element(By.ID, "qmc.actionbar.task.start").find_element(By.TAG_NAME, "button")
                    driver.execute_script("arguments[0].click();", start_button)
                    
                    time.sleep(5)
                    print(f"▶️ Tarefa '{nome}' foi reiniciada com sucesso.")
                except Exception as e:
                    print(f"⚠️ Erro ao tentar clicar no botão Start da tarefa '{nome}': {e}")

        print(f"\n📋 Tarefas no QMC '{nome_sufixo}':")
        for status, tarefas in sorted(tarefas_por_status.items()):
            print(colorir(status, f"\n🔸 Status: {status} ({len(tarefas)} tarefa(s))"))
            for nome, _, data in tarefas:
                print(f" - {nome} | Última Execução: {data}")

        print("\n📊 Resumo:")
        resumo_linhas = []
        for status, tarefas in sorted(tarefas_por_status.items()):
            linha = f" - {status}: {len(tarefas)}"
            print(colorir(status, linha))
            resumo_linhas.append(linha)

        # Monta o resumo como string
        resumo_str = f"Resumo das tarefas QMC '{nome_sufixo}'\n" + "\n".join(resumo_linhas)
        return resumo_str

    finally:
        driver.quit()

def coletar_status_qmc():
    resumos = {}
    os.makedirs("errorlogs", exist_ok=True)
    os.makedirs("tasks_qmc", exist_ok=True)
    # Removida a limpeza de PDFs antigos, pois agora sobrescreve o arquivo do dia
    for qmc in QMCs:
        nome_sufixo = qmc["nome"]
        url_login = qmc["url_login"]
        url_tasks = qmc["url_tasks"]
        print(f"\n🌐 Iniciando sessão em: {url_login}")
        options = webdriver.ChromeOptions()
        options.add_argument("--start-maximized")
        options.add_argument("--incognito")
        options.add_experimental_option("prefs", {
            "download.default_directory": os.path.abspath("errorlogs"),
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
                        linha.click()
                        def is_row_selected():
                            if isinstance(linha, WebElement):
                                class_attr = linha.get_attribute("class")
                                return class_attr is not None and "row-selected" in class_attr
                            return False
                        WebDriverWait(driver, 5).until(lambda d: is_row_selected())
                        print(f"✅ Linha '{nome}' marcada como selecionada.")
                        time.sleep(2)
                        icone_info = colunas[4].find_element(By.CSS_SELECTOR, "i.icon-qmc-info")
                        if esperar_popover_abrir(icone_info):
                            print(f"✅ Log aberto para '{nome}'. Procurando botão de download...")
                            botao_log = WebDriverWait(driver, 10).until(
                                EC.element_to_be_clickable((By.XPATH, "//div[text()='Download script log']"))
                            )
                            botao_log.click()
                            print(f"📥 Log da tarefa '{nome}' baixado com sucesso.")
                            time.sleep(5)
                            download_dir = os.path.abspath("errorlogs")
                            tmp_encontrado = None
                            for _ in range(10):
                                arquivos = [f for f in os.listdir(download_dir) if f.endswith(".tmp")]
                                if arquivos:
                                    tmp_encontrado = max(arquivos, key=lambda f: os.path.getctime(os.path.join(download_dir, f)))
                                    break
                                time.sleep(1)
                            if tmp_encontrado:
                                caminho_antigo = os.path.join(download_dir, tmp_encontrado)
                                caminho_novo = os.path.join(download_dir, f"{nome}.txt")
                                try:
                                    os.rename(caminho_antigo, caminho_novo)
                                    print(f"📄 Log renomeado para: {caminho_novo}")
                                    try:
                                        WebDriverWait(driver, 10).until(
                                            lambda d: d.find_element(By.ID, "qmc.actionbar.task.start").find_element(By.TAG_NAME, "button").is_enabled()
                                        )
                                        start_button = driver.find_element(By.ID, "qmc.actionbar.task.start").find_element(By.TAG_NAME, "button")
                                        driver.execute_script("arguments[0].click();", start_button)
                                        time.sleep(5)
                                        print(f"▶️ Tarefa '{nome}' foi reiniciada com sucesso.")
                                    except Exception as e:
                                        print(f"⚠️ Erro ao tentar clicar no botão Start da tarefa '{nome}': {e}")
                                except Exception as e:
                                    print(f"⚠️ Erro ao renomear: {e}")
                            else:
                                print("⚠️ Nenhum arquivo .tmp encontrado para renomear.")
                        else:
                            print(f"⏱️ Timeout: Error log não abriu para '{nome}'")
                except Exception as e:
                    print(f"⚠️ Erro ao tentar baixar o log '{nome}'")
                    try:
                        WebDriverWait(driver, 10).until(
                            lambda d: d.find_element(By.ID, "qmc.actionbar.task.start").find_element(By.TAG_NAME, "button").is_enabled()
                        )
                        start_button = driver.find_element(By.ID, "qmc.actionbar.task.start").find_element(By.TAG_NAME, "button")
                        driver.execute_script("arguments[0].click();", start_button)
                        time.sleep(5)
                        print(f"▶️ Tarefa '{nome}' foi reiniciada com sucesso.")
                    except Exception as e:
                        print(f"⚠️ Erro ao tentar clicar no botão Start da tarefa '{nome}': {e}")
            print(f"\n📋 Tarefas no QMC '{nome_sufixo}':")
            for status, tarefas in sorted(tarefas_por_status.items()):
                print(colorir(status, f"\n🔸 Status: {status} ({len(tarefas)} tarefa(s))"))
                for nome, _, data in tarefas:
                    print(f" - {nome} | Última Execução: {data}")
            print("\n📊 Resumo:")
            resumo_linhas = []
            for status, tarefas in sorted(tarefas_por_status.items()):
                linha = f" - {status}: {len(tarefas)}"
                print(colorir(status, linha))
                resumo_linhas.append(linha)
            # Monta o resumo como string
            resumo_str = f"Resumo das tarefas QMC '{nome_sufixo}'\n" + "\n".join(resumo_linhas)
            resumos[nome_sufixo] = resumo_str
            # Geração de PDF ao final
            registros = [tarefa for tarefas in tarefas_por_status.values() for tarefa in tarefas]
            nome_arquivo = f"status_qlik_{nome_sufixo}_{hoje.strftime('%Y-%m-%d')}.pdf"
            caminho_pdf = os.path.join("tasks_qmc", nome_arquivo)
            env = Environment(loader=FileSystemLoader("."))
            template = env.get_template("template.html")
            html_renderizado = template.render(
                nome_sufixo=nome_sufixo,
                tarefas=registros
            )
            with open(caminho_pdf, "wb") as saida_pdf:
                pisa.CreatePDF(html_renderizado, dest=saida_pdf)
            print(f"\n 705 PDF gerado com xhtml2pdf: {caminho_pdf}")
        finally:
            driver.quit()
    return resumos

if __name__ == "__main__":
    coletar_status_qmc()
