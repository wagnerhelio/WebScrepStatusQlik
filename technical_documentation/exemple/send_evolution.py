import os
import shutil
from dotenv import load_dotenv
from evolutionapi.client import EvolutionClient
from evolutionapi.models.message import TextMessage, MediaMessage
from glob import glob
from crawler_qlik.status_qlik_task import (
    coletar_status_nprinting,
    coletar_status_qmc,
)

# Carrega variáveis do ambiente
load_dotenv()

evo_api_token = os.getenv("EVOLUTION_API_TOKEN")
evo_instance_id = os.getenv("EVOLUTION_INSTANCE_NAME")
evo_instance_token = os.getenv("EVOLUTION_INSTANCE_ID")
evo_grupo = os.getenv("EVO_DESTINO_GRUPO")  # Grupo padrão
evo_destino = os.getenv("EVO_DESTINO")      # Número individual

# Pastas de origem
pasta_compartilhada = r"\\relatorios\NPrintingServer\Relatorios"
def _resolve_reports_dir():
    env_dir = os.getenv("TASKS_DIR", "").strip().strip('"').strip("'")
    if env_dir:
        return env_dir
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    preferred = os.path.join(repo_root, "crawler_qlik", "reports_qlik")
    try:
        os.makedirs(preferred, exist_ok=True)
        return preferred
    except Exception:
        pass
    return "task" if (os.path.isdir("task") and not os.path.isdir("tasks")) else "tasks"

tasks_dir = _resolve_reports_dir()

pastas_envio = [
    os.path.join(os.path.dirname(__file__), "..", "crawler_qlik", "errorlogs"),
    tasks_dir,
    pasta_compartilhada
]

def get_resumos_concatenados():
    # Ordem desejada: relatorios, estatistica, paineis
    ordem = [
        (tasks_dir, "relatorios"),
        (tasks_dir, "estatistica"),
        (tasks_dir, "paineis"),
    ]
    blocos = []
    for pasta, sufixo in ordem:
        arquivos = [f for f in os.listdir(pasta) if f.endswith(".txt") and f"_{sufixo}_" in f]
        if not arquivos:
            continue
        # Pega o mais recente
        arquivos.sort(key=lambda n: os.path.getctime(os.path.join(pasta, n)), reverse=True)
        arq = arquivos[0]
        with open(os.path.join(pasta, arq), "r", encoding="utf-8") as f:
            conteudo = f.read().strip()
        blocos.append(conteudo)
    return "\n\n".join(blocos)

# Inicializa cliente Evolution
if not all([evo_api_token, evo_instance_id, evo_instance_token, (evo_grupo or evo_destino)]):
    print("❌ Variáveis de ambiente obrigatórias não definidas. Verifique o .env.")
    exit(1)

evo_api_token = str(evo_api_token)
evo_instance_id = str(evo_instance_id)
evo_instance_token = str(evo_instance_token)
evo_grupo = str(evo_grupo)

api_token = evo_api_token
instance_id = evo_instance_id
instance_token = evo_instance_token
grupo_num = str(evo_grupo) if evo_grupo else ""
destino_num = str(evo_destino) if evo_destino else ""

client = EvolutionClient(
    base_url="http://localhost:8080",
    api_token=api_token
)

# Gera os resumos em memória
resumos_nprinting = coletar_status_nprinting()  # {'relatorios': 'Resumo...'}
resumos_qmc = coletar_status_qmc()  # {'estatistica': 'Resumo...', 'paineis': 'Resumo...'}

# Monta o resumo na ordem desejada
blocos = []
if 'relatorios' in resumos_nprinting:
    blocos.append(resumos_nprinting['relatorios'])
if 'estatistica' in resumos_qmc:
    blocos.append(resumos_qmc['estatistica'])
if 'paineis' in resumos_qmc:
    blocos.append(resumos_qmc['paineis'])
resumo_concat = "\n\n".join(blocos)

# Função auxiliar para envio de arquivo (declarada antes do uso)
def enviar_arquivo_para(destinatario, caminho_completo):
    nome_arquivo = os.path.basename(caminho_completo)
    ext = os.path.splitext(nome_arquivo)[1].lower()
    mimetype = "application/pdf" if ext == ".pdf" else "text/plain"

    media_message = MediaMessage(
        number=destinatario,
        mediatype="document",
        mimetype=mimetype,
        caption=f"📎 {nome_arquivo}",
        fileName=nome_arquivo
    )

    response = client.messages.send_media(
        instance_id,
        media_message,
        instance_token,
        caminho_completo
    )
    print(f"📨 Enviado para {destinatario}: {nome_arquivo} | Resultado: {response}")

for destino in [destino_num, grupo_num]:
    if not destino:
        print(f"⚠️ Destino não definido: {destino}")
        continue
    try:
        client.messages.send_text(
            instance_id,
            TextMessage(
                number=destino,
                text=resumo_concat
            ),
            instance_token
        )
        print(f"✅ Resumo concatenado enviado para: {destino}")
    except Exception as e:
        print(f"❌ Erro ao enviar resumo para {destino}: {e}")

# Envio dos arquivos PDF de status das ETLs (na ordem relatorios, estatistica, paineis)
def enviar_pdfs_status():
    ordem = [
        ("tasks", "relatorios"),
        ("tasks", "estatistica"),
        ("tasks", "paineis"),
    ]
    arquivos_pdf = []
    for pasta, sufixo in ordem:
        arquivos = [f for f in os.listdir(pasta) if f.endswith(".pdf") and f"_{sufixo}_" in f]
        if not arquivos:
            continue
        arquivos.sort(key=lambda n: os.path.getctime(os.path.join(pasta, n)), reverse=True)
        arq = os.path.join(pasta, arquivos[0])
        arquivos_pdf.append(arq)
    for arquivo in arquivos_pdf:
        for destino in [destino_num, grupo_num]:
            try:
                enviar_arquivo_para(destino, arquivo)
            except Exception as e:
                print(f"❌ Erro ao enviar PDF de status {arquivo} para {destino}: {e}")

enviar_pdfs_status()

# Envio dos logs de erro (errorlogs)
def enviar_logs_erro():
    pastas_erro = [os.path.join(os.path.dirname(__file__), "..", "crawler_qlik", "errorlogs")]
    arquivos_erro = []
    for pasta in pastas_erro:
        if not os.path.exists(pasta):
            continue
        arquivos = [os.path.join(pasta, f) for f in os.listdir(pasta) if os.path.isfile(os.path.join(pasta, f))]
        arquivos_erro.extend(arquivos)
    if arquivos_erro:
        for arquivo in arquivos_erro:
            for destino in [destino_num, grupo_num]:
                try:
                    enviar_arquivo_para(destino, arquivo)
                except Exception as e:
                    print(f"❌ Erro ao enviar log de erro {arquivo} para {destino}: {e}")
    else:
        for destino in [destino_num, grupo_num]:
            try:
                client.messages.send_text(
                    instance_id,
                    TextMessage(
                        number=destino,
                        text="Nenhum erro encontrado nas ETLs."
                    ),
                    instance_token
                )
                print(f"✅ Mensagem de nenhum erro enviada para: {destino}")
            except Exception as e:
                print(f"❌ Erro ao enviar mensagem de nenhum erro para {destino}: {e}")

enviar_logs_erro()

# Envio dos relatórios da pasta compartilhada
def enviar_relatorios_compartilhados():
    pasta = pasta_compartilhada
    if not os.path.exists(pasta):
        print(f"⚠️ Pasta compartilhada não encontrada: {pasta}")
        return
    arquivos = [os.path.join(pasta, f) for f in os.listdir(pasta) if os.path.isfile(os.path.join(pasta, f))]
    if not arquivos:
        print(f"📂 Nenhum relatório para enviar em: {pasta}")
        return
    for arquivo in arquivos:
        for destino in [destino_num, grupo_num]:
            try:
                enviar_arquivo_para(destino, arquivo)
            except Exception as e:
                print(f"❌ Erro ao enviar relatório compartilhado {arquivo} para {destino}: {e}")

enviar_relatorios_compartilhados()

# Envio e limpeza das pastas
for pasta in pastas_envio:
    if not os.path.exists(pasta):
        print(f"⚠️ Pasta não encontrada: {pasta}")
        continue

    arquivos = [
        os.path.join(pasta, f)
        for f in os.listdir(pasta)
        if os.path.isfile(os.path.join(pasta, f))
    ]

    if not arquivos:
        print(f"📂 Nenhum arquivo para enviar em: {pasta}")
        continue

    for arquivo in arquivos:
        try:
            for destino in [destino_num, grupo_num]:
                enviar_arquivo_para(destino, arquivo)
        except Exception as e:
            print(f"❌ Erro ao enviar {arquivo}: {e}")

    # Limpeza da pasta
    for arquivo in arquivos:
        try:
            os.remove(arquivo)
        except Exception as e:
            print(f"❌ Erro ao remover {arquivo}: {e}")

    print(f"🧹 Pasta limpa: {pasta}")

print("\n✅ Processo finalizado.")
