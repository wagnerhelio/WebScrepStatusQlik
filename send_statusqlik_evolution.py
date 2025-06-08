import os
from dotenv import load_dotenv
from evolutionapi.client import EvolutionClient
from evolutionapi.models.message import TextMessage, MediaMessage

# Carrega variáveis do .env
load_dotenv()

evo_api_token = os.getenv("EVOLUTION_API_TOKEN")
evo_instance_id = os.getenv("EVOLUTION_INSTANCE_NAME")
evo_instance_token = os.getenv("EVOLUTION_INSTANCE_ID")
evo_destino = os.getenv("EVO_DESTINO")  # Ex: 5562992422540
pasta_pdfs = os.getenv("EVO_TASKS_QMC")  # Ex: tasks_qmc

client = EvolutionClient(
    base_url="http://localhost:8080",
    api_token=evo_api_token
)

# Envia mensagem inicial
text_message = TextMessage(
    number=evo_destino,
    text="📎 Enviando relatórios QMC gerados em PDF."
)
client.messages.send_text(
    evo_instance_id,
    text_message,
    evo_instance_token
)

# Percorre e envia todos os PDFs
if not os.path.exists(pasta_pdfs):
    print(f"❌ Pasta '{pasta_pdfs}' não encontrada.")
    exit()

pdfs = [f for f in os.listdir(pasta_pdfs) if f.lower().endswith(".pdf")]
if not pdfs:
    print("⚠️ Nenhum PDF encontrado para envio.")
else:
    for pdf in pdfs:
        caminho_pdf = os.path.join(pasta_pdfs, pdf)
        print(f"📤 Enviando: {pdf}")

        media_message = MediaMessage(
            number=evo_destino,
            mediatype="document",
            mimetype="application/pdf",
            caption=f"Relatório: {pdf}",
            fileName=pdf,
            media=""
        )

        response = client.messages.send_media(
            evo_instance_id,
            media_message,
            evo_instance_token,
            caminho_pdf
        )
        print(f"📨 Resultado: {response}")
