import os
import time
import locale
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
from bs4 import BeautifulSoup

# Inicialização
init(autoreset=True)
load_dotenv()

# Locale para datas em português
try:
    locale.setlocale(locale.LC_TIME, 'pt_BR.UTF-8')
except:
    try:
        locale.setlocale(locale.LC_TIME, 'pt_BR')
    except:
        print("⚠️ Locale 'pt_BR' não disponível. Datas podem não ser interpretadas corretamente.")

# Variáveis de ambiente
usuario = os.getenv("QLIK_USUARIO")
senha = os.getenv("QLIK_SENHA")
email = os.getenv("QLIK_EMAIL")
CAMINHO_CHROMEDRIVER = os.getenv("CHROMEDRIVER")

QMCs = [
    {"nome": "estatistica", "url_login": os.getenv("QLIK_QMC_QAP"), "url_tasks": os.getenv("QLIK_TASK_QAP")},
    {"nome": "paineis", "url_login": os.getenv("QLIK_QMC_HUB"), "url_tasks": os.getenv("QLIK_TASK_HUB")}
]
NPRINTINGs = [
    {"nome": "relatorios", "url_login": os.getenv("QLIK_NPRINT"), "url_tasks": os.getenv("QLIK_NPRINT_TASK")}
]

status_map_qmc = {
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
status_map_nprinting = {
    "label label-danger": "Falha",
    "label label-success": "Concluída",
    "label label-warning": "Aviso",
    "label label-default": "Em fila",
    "label label-info blink": "Em execução"
}

cores = {
    "Success": Fore.GREEN,
    "Concluída": Fore.GREEN,
    "Em rota de atualização": Fore.BLUE,
    "Em execução": Fore.BLUE,
    "Em fila": Fore.BLUE,
    "Failed": Fore.RED,
    "Falha": Fore.RED,
    "Error": Fore.RED,
    "Aviso": Fore.YELLOW,
    "Outros": Fore.YELLOW,
}

def colorir(status, texto):
    return cores.get(status, Fore.YELLOW) + texto + Style.RESET_ALL

def esperar_popover_abrir(icone, max_tentativas=10):
    for i in range(max_tentativas):
        try:
            icone.click()
            time.sleep(1.5)
            if icone.get_attribute("data-ongoing") == "true":
                return True
        except Exception as e:
            print(f"⚠️ Erro ao clicar no ícone: {e}")
        time.sleep(1)
    return False

def coletar_status_qmc():
    resumos = {}
    os.makedirs("errorlogs", exist_ok=True)
    os.makedirs("tasks", exist_ok=True)
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
                    status = status_map_qmc.get(classe_status, "Outros")
                    if status == "Success":
                        try:
                            data_execucao = datetime.strptime(ultima_execucao[:16], "%Y-%m-%d %H:%M").date()
                            if data_execucao != hoje:
                                status = "Em rota de atualização"
                        except:
                            status = "Em rota de atualização"
                    tarefas_por_status.setdefault(status, []).append([nome, status, ultima_execucao])
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
            resumo_str = f"Resumo das tarefas QMC '{nome_sufixo}'\n" + "\n".join(resumo_linhas)
            resumos[nome_sufixo] = resumo_str
            registros = [tarefa for tarefas in tarefas_por_status.values() for tarefa in tarefas]
            nome_arquivo = f"status_qlik_{nome_sufixo}_{hoje.strftime('%Y-%m-%d')}.pdf"
            caminho_pdf = os.path.join("tasks", nome_arquivo)
            env = Environment(loader=FileSystemLoader("."))
            template = env.get_template("template.html")
            html_renderizado = template.render(
                nome_sufixo=nome_sufixo,
                tarefas=registros
            )
            with open(caminho_pdf, "wb") as saida_pdf:
                pisa.CreatePDF(html_renderizado, dest=saida_pdf)
            print(f"\n✅ PDF gerado com xhtml2pdf: {caminho_pdf}")
        finally:
            driver.quit()
    return resumos

def coletar_status_nprinting():
    resumos = {}
    os.makedirs("errorlogs", exist_ok=True)
    os.makedirs("tasks", exist_ok=True)
    for nprinting in NPRINTINGs:
        nome_sufixo = nprinting["nome"]
        url_login = nprinting["url_login"]
        url_tasks = nprinting["url_tasks"]
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
            wait = WebDriverWait(driver, 10)
            campo_email = wait.until(EC.presence_of_element_located((By.ID, "email")))
            campo_email.send_keys(email)
            campo_senha = wait.until(EC.presence_of_element_located((By.ID, "password")))
            campo_senha.send_keys(senha)
            campo_senha.send_keys(Keys.ENTER)
            print("✅ Login enviado.")
            time.sleep(5)
            driver.get(url_tasks)
            print("📄 Carregando tarefas...")
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table.table tbody tr.ng-scope")))
            time.sleep(1)
            hoje = date.today()
            tarefas_por_status = {}
            linhas = driver.find_elements(By.CSS_SELECTOR, "table.table tbody tr.ng-scope")
            for linha in linhas:
                try:
                    colunas = linha.find_elements(By.TAG_NAME, "td")
                    if len(colunas) < 6:
                        continue
                    nome = colunas[0].text.strip()
                    a_tag = colunas[0].find_element(By.TAG_NAME, "a")
                    href = a_tag.get_attribute("href")
                    tipo = colunas[1].text.strip()
                    status_texto = colunas[2].text.strip()
                    classe_status = colunas[2].find_element(By.TAG_NAME, "span").get_attribute("class")
                    status = status_map_nprinting.get(classe_status.strip(), status_texto)
                    progresso = colunas[3].text.strip()
                    criado = colunas[4].text.strip()
                    atualizado = colunas[5].text.strip()
                    try:
                        data_execucao = datetime.strptime(criado, "%d de %B de %Y às %H:%M").date()
                    except Exception as e:
                        print(f"⚠️ Erro ao converter data '{criado}': {e}")
                        continue
                    if data_execucao != hoje:
                        continue  # ignora tarefas que não são de hoje
                    tarefas_por_status.setdefault(status, []).append([
                        nome, tipo, status, progresso, criado, atualizado
                    ])
                    if status == "Falha":
                        print(f"\n⚠️ Tentando baixar log da tarefa '{nome}'...")
                        driver.execute_script("window.open(arguments[0]);", href)
                        driver.switch_to.window(driver.window_handles[-1])
                        time.sleep(3)
                        soup = BeautifulSoup(driver.page_source, "html.parser")
                        log_linhas = soup.select("table#executionsLogTable tbody tr")
                        if log_linhas:
                            log_path = f"errorlogs/{nome}_log.txt"
                            with open(log_path, "w", encoding="utf-8") as f:
                                for linha_log in log_linhas:
                                    tds = linha_log.find_all("td")
                                    if len(tds) == 3:
                                        f.write(f"[{tds[0].text.strip()}] {tds[1].text.strip()} - {tds[2].text.strip()}\n")
                            print(f"📁 Log salvo: {log_path}")
                        driver.close()
                        driver.switch_to.window(driver.window_handles[0])
                except Exception as e:
                    print(f"⚠️ Erro ao processar linha: {e}")
            print(f"\n📋 Tarefas no QMC '{nome_sufixo}':")
            for status, tarefas in sorted(tarefas_por_status.items()):
                print(colorir(status, f"\n🔸 Status: {status} ({len(tarefas)} tarefa(s))"))
                for tarefa in tarefas:
                    print(f" - {tarefa[0]} | Última Execução: {tarefa[4]}")
            print("\n📊 Resumo:")
            resumo_linhas = []
            for status, tarefas in sorted(tarefas_por_status.items()):
                linha = f" - {status}: {len(tarefas)}"
                print(colorir(status, linha))
                resumo_linhas.append(linha)
            resumo_str = f"Resumo das tarefas QMC '{nome_sufixo}'\n" + "\n".join(resumo_linhas)
            resumos[nome_sufixo] = resumo_str
            registros = [tarefa for tarefas in tarefas_por_status.values() for tarefa in tarefas]
            nome_arquivo = f"status_nprinting_{nome_sufixo}_{hoje.strftime('%Y-%m-%d')}.pdf"
            caminho_pdf = os.path.join("tasks", nome_arquivo)
            env = Environment(loader=FileSystemLoader("."))
            template = env.get_template("template_nprinting.html")
            html_renderizado = template.render(
                nome_sufixo=nome_sufixo,
                tarefas=registros
            )
            with open(caminho_pdf, "wb") as saida_pdf:
                pisa.CreatePDF(html_renderizado, dest=saida_pdf)
            print(f"\n✅ PDF gerado com xhtml2pdf: {caminho_pdf}")
        finally:
            driver.quit()
    return resumos

def coletar_status():
    resumos = {}
    resumos.update(coletar_status_qmc())
    resumos.update(coletar_status_nprinting())
    return resumos

if __name__ == "__main__":
    coletar_status() 