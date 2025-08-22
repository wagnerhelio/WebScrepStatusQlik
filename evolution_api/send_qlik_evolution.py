"""
Script para envio de relatórios e status Qlik via Evolution API
Envia resumos de status, arquivos PDF e logs de erro para grupos e números específicos
"""

import os
import shutil
from dotenv import load_dotenv
from evolutionapi.client import EvolutionClient
from evolutionapi.models.message import TextMessage, MediaMessage
from glob import glob
from crawler_qlik.status_qlik_task import (coletar_status_nprinting, coletar_status_qmc)

# =============================================================================
# CONFIGURAÇÃO E VARIÁVEIS DE AMBIENTE
# =============================================================================

# Carrega variáveis do ambiente do arquivo .env
load_dotenv()

# Configurações da Evolution API
evo_api_token = os.getenv("EVOLUTION_API_TOKEN")
evo_instance_id = os.getenv("EVOLUTION_INSTANCE_NAME")
evo_instance_token = os.getenv("EVOLUTION_INSTANCE_ID")
evo_grupo = os.getenv("EVO_DESTINO_GRUPO")  # Grupo padrão para envio
evo_destino = os.getenv("EVO_DESTINO")      # Número individual para envio

# =============================================================================
# CONFIGURAÇÃO DOS DIRETÓRIOS
# =============================================================================

# Diretório da pasta compartilhada (NPrinting Server)
pasta_compartilhada = r"\\relatorios\NPrintingServer\Relatorios"

def _resolve_reports_dir():
    """
    Resolve o diretório de relatórios com fallback para diretórios padrão.
    
    Returns:
        str: Caminho do diretório de relatórios
    """
    # Tenta usar variável de ambiente primeiro
    env_dir = os.getenv("TASKS_DIR", "").strip().strip('"').strip("'")
    if env_dir:
        return env_dir
    
    # Fallback para diretório padrão do projeto
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    preferred = os.path.join(repo_root, "crawler_qlik", "reports_qlik")
    
    try:
        os.makedirs(preferred, exist_ok=True)
        return preferred
    except Exception:
        pass
    
    # Último fallback para diretórios padrão
    return "task" if (os.path.isdir("task") and not os.path.isdir("tasks")) else "tasks"

# Resolve o diretório de tarefas/relatórios
tasks_dir = _resolve_reports_dir()

# Lista de pastas para envio (atualizada conforme solicitado)
pastas_envio = [
    os.path.join(os.path.dirname(__file__), "..", "crawler_qlik", "reports_qlik"),  # @reports_qlik/
    os.path.join(os.path.dirname(__file__), "..", "crawler_qlik", "errorlogs"),    # @errorlogs/
    pasta_compartilhada  # Pasta compartilhada NPrinting
]

# =============================================================================
# VALIDAÇÃO DAS CONFIGURAÇÕES
# =============================================================================

# Verifica se todas as variáveis obrigatórias estão definidas
if not all([evo_api_token, evo_instance_id, evo_instance_token, (evo_grupo or evo_destino)]):
    print("❌ Variáveis de ambiente obrigatórias não definidas. Verifique o arquivo .env")
    exit(1)

# Converte para string e remove espaços em branco
evo_api_token = str(evo_api_token).strip()
evo_instance_id = str(evo_instance_id).strip()
evo_instance_token = str(evo_instance_token).strip()
evo_grupo = str(evo_grupo).strip() if evo_grupo else ""

# =============================================================================
# INICIALIZAÇÃO DO CLIENTE EVOLUTION
# =============================================================================

# Inicializa o cliente da Evolution API
client = EvolutionClient(
    base_url="http://localhost:8080",
    api_token=evo_api_token
)

# =============================================================================
# COLETA DE DADOS DE STATUS
# =============================================================================

def coletar_resumos_status():
    """
    Coleta resumos de status do NPrinting e QMC.
    
    Returns:
        dict: Dicionário com resumos organizados por categoria
    """
    # Coleta status do NPrinting (relatórios)
    resumos_nprinting = coletar_status_nprinting()
    
    # Coleta status do QMC (estatísticas e painéis)
    resumos_qmc = coletar_status_qmc()
    
    return {
        'nprinting': resumos_nprinting,
        'qmc': resumos_qmc
    }

def montar_resumo_concatenado(resumos):
    """
    Monta o resumo concatenado na ordem específica: relatórios, estatísticas, painéis.
    
    Args:
        resumos (dict): Dicionário com resumos coletados
        
    Returns:
        str: Resumo concatenado em formato de texto
    """
    blocos = []
    
    # Ordem desejada: relatórios (NPrinting), estatísticas (QMC), painéis (QMC)
    if 'relatorios' in resumos['nprinting']:
        blocos.append(resumos['nprinting']['relatorios'])
    
    if 'estatistica' in resumos['qmc']:
        blocos.append(resumos['qmc']['estatistica'])
    
    if 'paineis' in resumos['qmc']:
        blocos.append(resumos['qmc']['paineis'])
    
    return "\n\n".join(blocos)

# =============================================================================
# FUNÇÕES DE ENVIO
# =============================================================================

def enviar_arquivo_para(destinatario, caminho_completo):
    """
    Envia um arquivo para um destinatário específico via Evolution API.
    
    Args:
        destinatario (str): Número ou ID do destinatário
        caminho_completo (str): Caminho completo do arquivo a ser enviado
    """
    nome_arquivo = os.path.basename(caminho_completo)
    ext = os.path.splitext(nome_arquivo)[1].lower()
    
    # Define o tipo MIME baseado na extensão do arquivo
    mimetype = "application/pdf" if ext == ".pdf" else "text/plain"
    
    # Cria mensagem de mídia
    media_message = MediaMessage(
        number=destinatario,
        mediatype="document",
        mimetype=mimetype,
        caption=f"📎 {nome_arquivo}",
        fileName=nome_arquivo
    )
    
    try:
        # Envia o arquivo via Evolution API
        response = client.messages.send_media(
            evo_instance_id,
            media_message,
            evo_instance_token,
            caminho_completo
        )
        print(f"📨 Enviado para {destinatario}: {nome_arquivo} | Resultado: {response}")
    except Exception as e:
        print(f"❌ Erro ao enviar arquivo {nome_arquivo} para {destinatario}: {e}")

def enviar_mensagem_texto(destinatario, texto):
    """
    Envia uma mensagem de texto para um destinatário específico.
    
    Args:
        destinatarario (str): Número ou ID do destinatário
        texto (str): Texto da mensagem a ser enviada
    """
    try:
        client.messages.send_text(
            evo_instance_id,
            TextMessage(
                number=destinatario,
                text=texto
            ),
            evo_instance_token
        )
        print(f"✅ Mensagem de texto enviada para: {destinatario}")
    except Exception as e:
        print(f"❌ Erro ao enviar mensagem de texto para {destinatario}: {e}")

def enviar_para_todos_destinos(func, *args, **kwargs):
    """
    Executa uma função para todos os destinos configurados.
    
    Args:
        func: Função a ser executada
        *args: Argumentos posicionais para a função
        **kwargs: Argumentos nomeados para a função
    """
    destinos = [evo_destino, evo_grupo]
    
    for destino in destinos:
        if not destino:
            print(f"⚠️ Destino não definido: {destino}")
            continue
        
        try:
            func(destino, *args, **kwargs)
        except Exception as e:
            print(f"❌ Erro ao processar destino {destino}: {e}")

# =============================================================================
# ENVIO DE RESUMOS DE STATUS
# =============================================================================

def enviar_resumos_status():
    """Envia resumos concatenados de status para todos os destinos."""
    print("📊 Coletando resumos de status...")
    
    # Coleta os resumos
    resumos = coletar_resumos_status()
    
    # Monta o resumo concatenado
    resumo_concat = montar_resumo_concatenado(resumos)
    
    # Envia para todos os destinos
    enviar_para_todos_destinos(enviar_mensagem_texto, resumo_concat)

# =============================================================================
# ENVIO DE ARQUIVOS PDF DE STATUS
# =============================================================================

def enviar_pdfs_status():
    """Envia arquivos PDF de status das ETLs na ordem especificada."""
    print("📄 Enviando arquivos PDF de status...")
    
    # Ordem desejada: relatórios, estatísticas, painéis
    ordem = [
        ("reports_qlik", "relatorios"),
        ("reports_qlik", "estatistica"),
        ("reports_qlik", "paineis"),
    ]
    
    arquivos_pdf = []
    
    # Busca arquivos PDF em cada categoria
    for pasta, sufixo in ordem:
        pasta_completa = os.path.join(os.path.dirname(__file__), "..", "crawler_qlik", pasta)
        
        if not os.path.exists(pasta_completa):
            continue
            
        arquivos = [
            f for f in os.listdir(pasta_completa) 
            if f.endswith(".pdf") and f"_{sufixo}_" in f
        ]
        
        if not arquivos:
            continue
            
        # Pega o arquivo mais recente
        arquivos.sort(key=lambda n: os.path.getctime(os.path.join(pasta_completa, n)), reverse=True)
        arq = os.path.join(pasta_completa, arquivos[0])
        arquivos_pdf.append(arq)
    
    # Envia cada arquivo PDF
    for arquivo in arquivos_pdf:
        enviar_para_todos_destinos(enviar_arquivo_para, arquivo)

# =============================================================================
# ENVIO DE LOGS DE ERRO
# =============================================================================

def enviar_logs_erro():
    """Envia logs de erro das ETLs para todos os destinos."""
    print("📋 Enviando logs de erro...")
    
    pasta_erro = os.path.join(os.path.dirname(__file__), "..", "crawler_qlik", "errorlogs")
    
    if not os.path.exists(pasta_erro):
        print(f"⚠️ Pasta de logs de erro não encontrada: {pasta_erro}")
        return
    
    # Lista todos os arquivos de erro
    arquivos_erro = [
        os.path.join(pasta_erro, f) 
        for f in os.listdir(pasta_erro) 
        if os.path.isfile(os.path.join(pasta_erro, f))
    ]
    
    if arquivos_erro:
        # Envia cada arquivo de erro
        for arquivo in arquivos_erro:
            enviar_para_todos_destinos(enviar_arquivo_para, arquivo)
    else:
        # Envia mensagem de que não há erros
        mensagem = "✅ Nenhum erro encontrado nas ETLs."
        enviar_para_todos_destinos(enviar_mensagem_texto, mensagem)

# =============================================================================
# ENVIO DE RELATÓRIOS COMPARTILHADOS
# =============================================================================

def enviar_relatorios_compartilhados():
    """Envia relatórios da pasta compartilhada NPrinting."""
    print("📁 Enviando relatórios da pasta compartilhada...")
    
    if not os.path.exists(pasta_compartilhada):
        print(f"⚠️ Pasta compartilhada não encontrada: {pasta_compartilhada}")
        return
    
    # Lista todos os arquivos da pasta compartilhada
    arquivos = [
        os.path.join(pasta_compartilhada, f) 
        for f in os.listdir(pasta_compartilhada) 
        if os.path.isfile(os.path.join(pasta_compartilhada, f))
    ]
    
    if not arquivos:
        print(f"📂 Nenhum relatório para enviar em: {pasta_compartilhada}")
        return
    
    # Envia cada arquivo
    for arquivo in arquivos:
        enviar_para_todos_destinos(enviar_arquivo_para, arquivo)

# =============================================================================
# LIMPEZA DAS PASTAS APÓS ENVIO
# =============================================================================

def limpar_pastas_apos_envio():
    """Limpa as pastas após o envio bem-sucedido dos arquivos."""
    print("🧹 Limpando pastas após envio...")
    
    for pasta in pastas_envio:
        if not os.path.exists(pasta):
            print(f"⚠️ Pasta não encontrada: {pasta}")
            continue
        
        # Lista todos os arquivos da pasta
        arquivos = [
            os.path.join(pasta, f)
            for f in os.listdir(pasta)
            if os.path.isfile(os.path.join(pasta, f))
        ]
        
        if not arquivos:
            print(f"📂 Nenhum arquivo para limpar em: {pasta}")
            continue
        
        # Remove cada arquivo
        for arquivo in arquivos:
            try:
                os.remove(arquivo)
                print(f"🗑️ Arquivo removido: {os.path.basename(arquivo)}")
            except Exception as e:
                print(f"❌ Erro ao remover {arquivo}: {e}")
        
        print(f"🧹 Pasta limpa: {pasta}")

# =============================================================================
# FUNÇÃO PRINCIPAL
# =============================================================================

def main():
    """Função principal que executa todo o fluxo de envio."""
    print("🚀 Iniciando processo de envio via Evolution API...")
    
    try:
        # 1. Envia resumos de status
        enviar_resumos_status()
        
        # 2. Envia arquivos PDF de status
        enviar_pdfs_status()
        
        # 3. Envia logs de erro
        enviar_logs_erro()
        
        # 4. Envia relatórios da pasta compartilhada
        enviar_relatorios_compartilhados()
        
        # 5. Limpa as pastas após envio
        limpar_pastas_apos_envio()
        
        print("\n✅ Processo finalizado com sucesso!")
        
    except Exception as e:
        print(f"\n❌ Erro durante a execução: {e}")
        raise

# =============================================================================
# EXECUÇÃO DO SCRIPT
# =============================================================================

if __name__ == "__main__":
    main()
