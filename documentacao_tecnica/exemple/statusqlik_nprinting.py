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
from colorama import init, Fore, Style
from xhtml2pdf import pisa
from jinja2 import Environment, FileSystemLoader
from bs4 import BeautifulSoup

# Define locale para parsing de datas em português
try:
    locale.setlocale(locale.LC_TIME, 'pt_BR.UTF-8')
except:
    try:
        locale.setlocale(locale.LC_TIME, 'pt_BR')
    except:
        print("⚠️ Locale 'pt_BR' não disponível. Datas podem não ser interpretadas corretamente.")

init(autoreset=True)
load_dotenv()

email = os.getenv("QLIK_EMAIL")
senha = os.getenv("QLIK_SENHA")
CAMINHO_CHROMEDRIVER = os.getenv("CHROMEDRIVER")

NPRINTINGs = [
    {"nome": "relatorios", "url_login": os.getenv("QLIK_NPRINT"), "url_tasks": os.getenv("QLIK_NPRINT_TASK")}
]

status_map = {
    "label label-danger": "Falha",
    "label label-success": "Concluída",
    "label label-warning": "Aviso",
    "label label-default": "Em fila",
    "label label-info blink": "Em execução"
}

cores = {
    "Concluída": Fore.GREEN,
    "Em execução": Fore.BLUE,
    "Em fila": Fore.BLUE,
    "Falha": Fore.RED,
    "Aviso": Fore.YELLOW,
}

def colorir(status, texto):
    return cores.get(status, Fore.YELLOW) + texto + Style.RESET_ALL

def coletar_status(nome_sufixo, url_login, url_tasks):
    print(f"\n🌐 Iniciando sessão em: {url_login}")

    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_argument("--incognito")
    options.add_experimental_option("prefs", {
        "download.default_directory": os.path.abspath("errorlogs_nprinting"),
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
                status = status_map.get(classe_status.strip(), status_texto)
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
                        log_path = f"errorlogs_nprinting/{nome}_log.txt"
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
        for status, tarefas in sorted(tarefas_por_status.items()):
            print(colorir(status, f" - {status}: {len(tarefas)}"))

        registros = [tarefa for tarefas in tarefas_por_status.values() for tarefa in tarefas]
        nome_arquivo = f"status_nprinting_{nome_sufixo}_{hoje.strftime('%Y-%m-%d_%H-%M-%S')}.pdf"
        caminho_pdf = os.path.join("tasks_nprinting", nome_arquivo)

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

def coletar_status_nprinting():
    resumos = {}
    os.makedirs("errorlogs_nprinting", exist_ok=True)
    os.makedirs("tasks_nprinting", exist_ok=True)
    # Removida a limpeza de PDFs antigos, pois agora sobrescreve o arquivo do dia
    for nprinting in NPRINTINGs:
        nome_sufixo = nprinting["nome"]
        url_login = nprinting["url_login"]
        url_tasks = nprinting["url_tasks"]
        print(f"\n🌐 Iniciando sessão em: {url_login}")
        options = webdriver.ChromeOptions()
        options.add_argument("--start-maximized")
        options.add_argument("--incognito")
        options.add_experimental_option("prefs", {
            "download.default_directory": os.path.abspath("errorlogs_nprinting"),
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
                    status = status_map.get(classe_status.strip(), status_texto)
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
                            log_path = f"errorlogs_nprinting/{nome}_log.txt"
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
            caminho_pdf = os.path.join("tasks_nprinting", nome_arquivo)
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

if __name__ == "__main__":
    coletar_status_nprinting()
