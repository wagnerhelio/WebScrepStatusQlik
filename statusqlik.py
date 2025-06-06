# 📦 Importações
import os
import time
import csv
from datetime import datetime
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# 🔐 Carregar variáveis do .env
load_dotenv()

# 🧪 Ler variáveis de ambiente
usuario = os.getenv("QLIK_USUARIO")
senha = os.getenv("QLIK_SENHA")
CAMINHO_CHROMEDRIVER = os.getenv("CHROMEDRIVER")

# ❗ Verifica se variáveis foram carregadas corretamente
if not usuario or not senha or not CAMINHO_CHROMEDRIVER:
    raise ValueError("❌ Verifique seu arquivo .env - variáveis ausentes ou incorretas.")

# 🧼 Converte \\ para \ no campo do usuário
usuario = usuario.encode().decode('unicode_escape')

# 🧭 Iniciar o Chrome
options = webdriver.ChromeOptions()
driver = webdriver.Chrome(service=Service(CAMINHO_CHROMEDRIVER), options=options)
wait = WebDriverWait(driver, 15)

try:
    # 1️⃣ Acessar tela de login
    driver.get("https://estatistica.ssp.go.gov.br/qmc")
    print("🔐 Aguardando campo de login...")

    # 2️⃣ Espera os campos de login
    campo_usuario = wait.until(EC.presence_of_element_located((By.NAME, "username")))
    campo_senha = wait.until(EC.presence_of_element_located((By.NAME, "pwd")))

    # 3️⃣ Preencher e submeter
    campo_usuario.send_keys(usuario)
    campo_senha.send_keys(senha)
    campo_senha.send_keys(Keys.ENTER)
    print(f"✅ Login enviado como {usuario}")
    time.sleep(5)

    # 4️⃣ Acessar página de tarefas
    driver.get("https://estatistica.ssp.go.gov.br/qmc/tasks")
    print("📄 Carregando tarefas...")
    time.sleep(5)

    # 5️⃣ Captura todas as linhas da tabela
    linhas = driver.find_elements(By.CSS_SELECTOR, "table.qmc-table-rows tbody tr")
    
    # 📂 Mapeamento de classes para status
    status_map = {
        "icon-qmc-task-finishedsuccess": "Success",
        "icon-qmc-task-failed": "Error",
        "icon-qmc-task-triggered": "Triggered",
        "icon-qmc-task-started": "Started",
        "icon-qmc-task-queued": "Queued",
        "icon-qmc-task-aborted": "Aborted",
        "icon-qmc-task-neverstarted": "Never started",
        "icon-qmc-task-skipped": "Skipped",
        "icon-qmc-task-reset": "Reset",
        "icon-qmc-task-retrying": "Retrying"
    }

    # 📦 Dicionário de tarefas agrupadas por status
    tarefas_por_status = {}

    # 6️⃣ Processar cada linha
    for linha in linhas:
        colunas = linha.find_elements(By.TAG_NAME, "td")
        if len(colunas) >= 7:
            nome = colunas[0].text.strip()

             # 📊 Extrair classe do ícone
            try:
                icone = colunas[4].find_element(By.CSS_SELECTOR, "i[class^='icon-qmc-task']")
                classe_status = icone.get_attribute("class").strip()
                status = status_map.get(classe_status, "[status não detectado]")
            except:
                status = "[status não detectado]"

            ultima_execucao = colunas[5].text.strip()
            registro = [nome, status, ultima_execucao]
            
            # Agrupar por status
            if status not in tarefas_por_status:
                tarefas_por_status[status] = []
            tarefas_por_status[status].append(registro)

    # 📊 Impressão por grupo
    print("\n📋 Tarefas agrupadas por status:")
    for status, tarefas in sorted(tarefas_por_status.items()):
        print(f"\n🔸 Status: {status} ({len(tarefas)} tarefa(s))")
        for nome, _, data in tarefas:
            print(f" - {nome} | Última Execução: {data}")

    # 💾 Exportar CSV
    nome_arquivo = f"status_qlik_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.csv"
    with open(nome_arquivo, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Nome da Tarefa", "Status", "Última Execução"])
        for status in sorted(tarefas_por_status.keys()):
            for registro in tarefas_por_status[status]:
                writer.writerow(registro)

    print(f"\n✅ Dados exportados para: {nome_arquivo}")

finally:
    # 🔚 Finaliza o navegador
    driver.quit()
