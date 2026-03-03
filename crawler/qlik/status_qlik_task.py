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
from pathlib import Path
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

def _resolve_chromedriver_path() -> str | None:
    """Resolve o caminho do ChromeDriver com base em variáveis e fallbacks locais."""
    try:
        env_path = os.getenv("CHROMEDRIVER", "").strip().strip('"').strip("'")
        candidates = []
        if env_path:
            candidates.append(Path(env_path))
        repo_root = Path(__file__).resolve().parent.parent
        candidates.append(repo_root / "chromedriver" / "chromedriver.exe")
        candidates.append(repo_root / "chromedriver.exe")
        for p in candidates:
            try:
                if p.is_file():
                    return str(p)
            except Exception:
                continue
    except Exception:
        pass
    return None

# Diretório de saída dos PDFs de status
def _resolve_reports_dir() -> str:
    env_dir = os.getenv("TASKS_DIR", "").strip().strip('"').strip("'")
    if env_dir:
        return env_dir
    repo_root = Path(__file__).resolve().parent.parent
    preferred = repo_root / "crawler_qlik" / "reports_qlik"
    try:
        preferred.mkdir(parents=True, exist_ok=True)
        return str(preferred)
    except Exception:
        pass
    # fallback para pastas antigas
    if os.path.isdir("task") and not os.path.isdir("tasks"):
        return "task"
    return "tasks"

TASKS_DIR = _resolve_reports_dir()

def _normalize_domain_user(value: str | None) -> str | None:
    if value is None:
        return None
    # Converte \\ para \ e remove espaços laterais
    return value.replace("\\\\", "\\").strip()

# Normaliza usuário do Qlik (aceita domini\\usuario ou dominio\usuario)
usuario = _normalize_domain_user(usuario)

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
    # resolve errorlogs sempre em crawler_qlik/errorlogs
    errorlogs_dir = Path(__file__).resolve().parent / "errorlogs"
    os.makedirs(errorlogs_dir, exist_ok=True)
    os.makedirs(TASKS_DIR, exist_ok=True)
    for qmc in QMCs:
        nome_sufixo = qmc["nome"]
        url_login = qmc["url_login"]
        url_tasks = qmc["url_tasks"]
        print(f"\n🌐 Iniciando sessão em: {url_login}")
        options = webdriver.ChromeOptions()
        options.add_argument("--start-maximized")
        options.add_argument("--incognito")
        options.add_experimental_option("prefs", {
            "download.default_directory": str(errorlogs_dir.resolve()),
        })
        driver_path = _resolve_chromedriver_path()
        if driver_path:
            driver = webdriver.Chrome(service=Service(driver_path), options=options)
        else:
            # fallback: deixa o Selenium Manager resolver
            driver = webdriver.Chrome(options=options)
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
            tarefas_falhadas = []  # Lista para armazenar tarefas que falharam
            
            # Primeira passada: identifica todas as tarefas e suas falhas
            for i, linha in enumerate(linhas):
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
                    
                    # Se a tarefa falhou, adiciona à lista para processamento posterior
                    if status == "Failed":
                        tarefas_falhadas.append({
                            'nome': nome,
                            'indice': i,
                            'linha': linha,
                            'colunas': colunas
                        })
                        
                except Exception as e:
                    print(f"⚠️ Erro ao processar linha {i}: {e}")
                    continue
            
            # Segunda passada: processa todas as tarefas falhadas
            if tarefas_falhadas:
                print(f"\n🔄 Encontradas {len(tarefas_falhadas)} tarefa(s) falhada(s). Iniciando processo de retry...")
                
                for tarefa_falhada in tarefas_falhadas:
                    nome = tarefa_falhada['nome']
                    print(f"\n⚠️ Processando tarefa falhada: '{nome}'")
                    
                    try:
                        # Recarrega a página para evitar stale elements
                        driver.refresh()
                        time.sleep(3)
                        
                        # Busca a linha novamente usando o nome da tarefa
                        linhas_atualizadas = driver.find_elements(By.CSS_SELECTOR, "table.qmc-table-rows tbody tr")
                        linha_atual = None
                        
                        for linha_atualizada in linhas_atualizadas:
                            try:
                                colunas_atualizadas = linha_atualizada.find_elements(By.TAG_NAME, "td")
                                if len(colunas_atualizadas) >= 7:
                                    nome_atualizado = colunas_atualizadas[0].text.strip()
                                    if nome_atualizado == nome:
                                        linha_atual = linha_atualizada
                                        break
                            except:
                                continue
                        
                        if linha_atual is None:
                            print(f"⚠️ Não foi possível encontrar a linha da tarefa '{nome}' após refresh")
                            continue
                        
                        # Scroll para a linha e clica nela
                        driver.execute_script("arguments[0].scrollIntoView({behavior: 'auto', block: 'center'});", linha_atual)
                        time.sleep(0.5)
                        linha_atual.click()
                        
                        # Verifica se a linha foi selecionada
                        def is_row_selected():
                            try:
                                class_attr = linha_atual.get_attribute("class")
                                return class_attr is not None and "row-selected" in class_attr
                            except:
                                return False
                        
                        WebDriverWait(driver, 5).until(lambda d: is_row_selected())
                        print(f"✅ Linha '{nome}' marcada como selecionada.")
                        time.sleep(2)
                        
                        # Tenta baixar o log primeiro
                        try:
                            colunas_atual = linha_atual.find_elements(By.TAG_NAME, "td")
                            if len(colunas_atual) >= 5:
                                icone_info = colunas_atual[4].find_element(By.CSS_SELECTOR, "i.icon-qmc-info")
                                if esperar_popover_abrir(icone_info):
                                    print(f"✅ Log aberto para '{nome}'. Procurando botão de download...")
                                    botao_log = WebDriverWait(driver, 10).until(
                                        EC.element_to_be_clickable((By.XPATH, "//div[text()='Download script log']"))
                                    )
                                    botao_log.click()
                                    print(f"📥 Log da tarefa '{nome}' baixado com sucesso.")
                                    time.sleep(5)
                                    
                                    # Renomeia o arquivo de log
                                    download_dir = str(errorlogs_dir.resolve())
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
                                        except Exception as e:
                                            print(f"⚠️ Erro ao renomear log: {e}")
                                    else:
                                        print("⚠️ Nenhum arquivo .tmp encontrado para renomear.")
                                else:
                                    print(f"⏱️ Timeout: Error log não abriu para '{nome}'")
                        except Exception as e:
                            print(f"⚠️ Erro ao baixar log da tarefa '{nome}': {e}")
                        
                        # Tenta reiniciar a tarefa
                        print(f"🔄 Tentando reiniciar tarefa '{nome}'...")
                        try:
                            # Aguarda o botão Start estar habilitado
                            WebDriverWait(driver, 10).until(
                                lambda d: d.find_element(By.ID, "qmc.actionbar.task.start").find_element(By.TAG_NAME, "button").is_enabled()
                            )
                            start_button = driver.find_element(By.ID, "qmc.actionbar.task.start").find_element(By.TAG_NAME, "button")
                            driver.execute_script("arguments[0].click();", start_button)
                            print(f"▶️ Botão Start clicado para tarefa '{nome}'.")
                            
                            # Aguarda um pouco para o status mudar
                            time.sleep(3)
                            
                            # Verifica se o status mudou para "Started" ou similar
                            try:
                                # Recarrega a página para verificar o novo status
                                driver.refresh()
                                time.sleep(3)
                                
                                # Busca a linha novamente para verificar o novo status
                                linhas_verificacao = driver.find_elements(By.CSS_SELECTOR, "table.qmc-table-rows tbody tr")
                                status_atualizado = None
                                
                                for linha_verificacao in linhas_verificacao:
                                    try:
                                        colunas_verificacao = linha_verificacao.find_elements(By.TAG_NAME, "td")
                                        if len(colunas_verificacao) >= 5:
                                            nome_verificacao = colunas_verificacao[0].text.strip()
                                            if nome_verificacao == nome:
                                                icone_status_verificacao = colunas_verificacao[4].find_element(By.CSS_SELECTOR, "i[class^='icon-qmc-task']")
                                                classe_status_verificacao = next((cls for cls in icone_status_verificacao.get_attribute("class").split() if cls.startswith("icon-qmc-task")), "")
                                                status_atualizado = status_map_qmc.get(classe_status_verificacao, "Outros")
                                                break
                                    except:
                                        continue
                                
                                if status_atualizado:
                                    if status_atualizado in ["Started", "Triggered"]:
                                        print(f"✅ Tarefa '{nome}' reiniciada com sucesso! Novo status: {status_atualizado}")
                                    else:
                                        print(f"⚠️ Tarefa '{nome}' pode não ter reiniciado corretamente. Status atual: {status_atualizado}")
                                else:
                                    print(f"⚠️ Não foi possível verificar o status atualizado da tarefa '{nome}'")
                                    
                            except Exception as e:
                                print(f"⚠️ Erro ao verificar status atualizado da tarefa '{nome}': {e}")
                            
                        except Exception as e:
                            print(f"❌ Erro ao tentar clicar no botão Start da tarefa '{nome}': {e}")
                            
                    except Exception as e:
                        print(f"❌ Erro geral ao processar tarefa falhada '{nome}': {e}")
                        # Tenta pelo menos reiniciar mesmo se o log falhar
                        try:
                            print(f"🔄 Tentativa de reinício direto para '{nome}'...")
                            WebDriverWait(driver, 10).until(
                                lambda d: d.find_element(By.ID, "qmc.actionbar.task.start").find_element(By.TAG_NAME, "button").is_enabled()
                            )
                            start_button = driver.find_element(By.ID, "qmc.actionbar.task.start").find_element(By.TAG_NAME, "button")
                            driver.execute_script("arguments[0].click();", start_button)
                            time.sleep(3)
                            print(f"▶️ Tarefa '{nome}' foi reiniciada (método direto).")
                        except Exception as e2:
                            print(f"❌ Falha total ao reiniciar tarefa '{nome}': {e2}")
                
                print(f"\n✅ Processamento de {len(tarefas_falhadas)} tarefa(s) falhada(s) concluído.")
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
            caminho_pdf = os.path.join(TASKS_DIR, nome_arquivo)
            templates_dir = Path(__file__).resolve().parent / "teamplate"
            env = Environment(loader=FileSystemLoader(str(templates_dir)))
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
    errorlogs_dir = Path(__file__).resolve().parent / "errorlogs"
    os.makedirs(errorlogs_dir, exist_ok=True)
    os.makedirs(TASKS_DIR, exist_ok=True)
    for nprinting in NPRINTINGs:
        nome_sufixo = nprinting["nome"]
        url_login = nprinting["url_login"]
        url_tasks = nprinting["url_tasks"]
        print(f"\n🌐 Iniciando sessão em: {url_login}")
        options = webdriver.ChromeOptions()
        options.add_argument("--start-maximized")
        options.add_argument("--incognito")
        options.add_experimental_option("prefs", {
            "download.default_directory": str(errorlogs_dir.resolve()),
        })
        driver_path = _resolve_chromedriver_path()
        if driver_path:
            driver = webdriver.Chrome(service=Service(driver_path), options=options)
        else:
            # fallback: deixa o Selenium Manager resolver
            driver = webdriver.Chrome(options=options)
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
                            log_path = str(errorlogs_dir / f"{nome}_log.txt")
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
            caminho_pdf = os.path.join(TASKS_DIR, nome_arquivo)
            templates_dir = Path(__file__).resolve().parent / "teamplate"
            env = Environment(loader=FileSystemLoader(str(templates_dir)))
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