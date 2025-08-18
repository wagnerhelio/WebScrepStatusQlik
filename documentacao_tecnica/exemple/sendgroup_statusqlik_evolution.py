import os
import shutil
from dotenv import load_dotenv
from evolutionapi.client import EvolutionClient
from evolutionapi.models.message import TextMessage, MediaMessage

# Carrega variáveis do ambiente
load_dotenv()

evo_api_token = os.getenv("EVOLUTION_API_TOKEN")
evo_instance_id = os.getenv("EVOLUTION_INSTANCE_NAME")
evo_instance_token = os.getenv("EVOLUTION_INSTANCE_ID")
evo_grupo = os.getenv("EVO_DESTINO_GRUPO")  # Grupo padrão

# Pastas de origem
pasta_compartilhada = r"\\relatorios\NPrintingServer\Relatorios"
pastas_envio = [
    "errorlogs",
    "errorlogs_nprinting",
    "tasks_nprinting",
    "tasks_qmc",
    pasta_compartilhada
]

# Inicializa cliente Evolution
client = EvolutionClient(
    base_url="http://localhost:8080",
    api_token=evo_api_token
)

# Mensagem inicial para ambos
for destino in [evo_grupo]:
    try:
        client.messages.send_text(
            evo_instance_id,
            TextMessage(
                number=destino,
                text="📤 Enviando relatórios e logs atualizados."
            ),
            evo_instance_token
        )
        print(f"✅ Mensagem enviada para: {destino}")
    except Exception as e:
        print(f"❌ Erro ao enviar mensagem para {destino}: {e}")

# Função auxiliar para envio de arquivo
def enviar_arquivo_para(destinatario, caminho_completo):
    nome_arquivo = os.path.basename(caminho_completo)
    ext = os.path.splitext(nome_arquivo)[1].lower()
    mimetype = "application/pdf" if ext == ".pdf" else "text/plain"

    media_message = MediaMessage(
        number=destinatario,
        mediatype="document",
        mimetype=mimetype,
        caption=f"📎 {nome_arquivo}",
        fileName=nome_arquivo,
        media=""
    )

    response = client.messages.send_media(
        evo_instance_id,
        media_message,
        evo_instance_token,
        caminho_completo
    )
    print(f"📨 Enviado para {destinatario}: {nome_arquivo} | Resultado: {response}")

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
            for destino in [evo_grupo]:
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
