import os
import time
from datetime import datetime
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

from xhtml2pdf import pisa
from jinja2 import Environment, FileSystemLoader

load_dotenv()

email = os.getenv("QLIK_EMAIL")
senha = os.getenv("QLIK_SENHA")
CAMINHO_CHROMEDRIVER = os.getenv("CHROMEDRIVER")
URL_NPRINT = os.getenv("QLIK_NPRINT_TASK")

NPRINTINGs = [
    {"nome": "relatorios", "url_login": os.getenv("QLIK_NPRINT"), "url_tasks": os.getenv("QLIK_NPRINT_TASK")}
]

status_map = {
    "label label-danger": "Falha",
    "label label-success": "Concluída",
    "label label-warning": "Aviso",
    "label label-default": "Em fila",
    "label label-info blink": "Em execução",
}

cores = {
    "Concluída": Fore.GREEN,
    "Em execução": Fore.BLUE,
    "Em fila": Fore.BLUE,
    "Falha": Fore.RED,
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
        time.sleep(2)
        driver.find_element(By.ID, "username-input").send_keys(email)
        campo_senha = driver.find_element(By.ID, "password-input")
        campo_senha.send_keys(senha)
        campo_senha.send_keys(Keys.ENTER)
        print("✅ Login enviado.")
        time.sleep(5)

        driver.get(url_tasks)
        print("📄 Carregando tarefas...")
        time.sleep(6)

        linhas = driver.find_elements(By.CSS_SELECTOR, "table.table tbody tr")
        hoje = date.today()
        tarefas_por_status = {}

        for linha in linhas:
            try:
                colunas = linha.find_elements(By.TAG_NAME, "tr")
                if len(colunas) < 7:
                    continue
                link_elem = colunas[0].find_element(By.TAG_NAME, "a")
                nome = link_elem.text.strip()
                href = link_elem.get_attribute("href")
                id_tarefa = href.split("/")[-1]
                url_log = f"{URL_BASE}/#/tasks/executions/{id_tarefa}"
                tipo = colunas[1].text.strip()
                status = colunas[2].text.strip()
                classe_status = next((cls for cls in icone_status.get_attribute("class").split() if cls.startswith("icon-qmc-task")), "")
                status = status_map.get(classe_status, "Outros")
                progresso = colunas[3].text.strip()
                criado = colunas[4].text.strip()
                atualizado = colunas[5].text.strip()             
                        
                if status == "Concluída":
                    try:
                        data_execucao = datetime.strptime(criado[:16], "%Y-%m-%d %H:%M").date()
                        if data_execucao != hoje:
                            status = "Em rota de atualização"
                    except:
                        status = "Em rota de atualização"

                tarefas_por_status.setdefault(status, []).append([nome, status, criado])

                # Baixar log se Failed
                if status == "Falha":
                    print(f"\n⚠️ Tentando baixar log da tarefa '{nome}'...")
                    href = a_tag.get_attribute("href")
                    a_tag = linha.find_element(By.TAG_NAME, "a")
                    driver.execute_script("arguments[0].scrollIntoView({behavior: 'auto', block: 'center'});", a_tag)
                    a_tag.click()
                    
                    # Troca para nova aba aberta pelo link
                    driver.switch_to.window(driver.window_handles[-1])
                    print(f"🔄 Mudando para a aba da tarefa '{nome}'...")

            except Exception as e:
                print(f"⚠️ Erro ao tentar baixar o log '{nome}'")
                
        print(f"\n📋 Tarefas no QMC '{nome_sufixo}':")
        for status, tarefas in sorted(tarefas_por_status.items()):
            print(colorir(status, f"\n🔸 Status: {status} ({len(tarefas)} tarefa(s))"))
            for nome, _, data in tarefas:
                print(f" - {nome} | Última Execução: {data}")

        print("\n📊 Resumo:")
        for status, tarefas in sorted(tarefas_por_status.items()):
            print(colorir(status, f" - {status}: {len(tarefas)}"))

        # Geração de PDF ao final
        registros = [tarefa for tarefas in tarefas_por_status.values() for tarefa in tarefas]
        nome_arquivo = f"status_nprinting_{nome_sufixo}_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.pdf"
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
        
os.makedirs("errorlogs_nprinting", exist_ok=True)
os.makedirs("tasks_nprinting", exist_ok=True)

for nprinting in NPRINTINGs:
    coletar_status(nprinting["nome"], nprinting["url_login"], nprinting["url_tasks"])