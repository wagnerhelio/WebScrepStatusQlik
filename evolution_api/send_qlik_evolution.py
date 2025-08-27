"""
Script para envio de relatórios e status Qlik via Evolution API
Envia resumos de status, arquivos PDF e logs de erro para grupos e números específicos
"""

import os
import sys
import shutil
import subprocess
from dotenv import load_dotenv

# Adiciona o diretório raiz do projeto ao sys.path para resolver imports
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.insert(0, project_root)

try:
    from evolutionapi.client import EvolutionClient
    from evolutionapi.models.message import TextMessage, MediaMessage
    from crawler_qlik.status_qlik_task import (coletar_status_nprinting, coletar_status_qmc)
    from crawler_qlik.network_config import setup_network_credentials, get_accessible_paths
except ImportError as e:
    print(f"❌ Erro ao importar módulos: {e}")
    print("💡 Certifique-se de que todas as dependências estão instaladas:")
    print("   pip install python-dotenv evolution-api")
    print("   E que o módulo crawler_qlik está acessível")
    sys.exit(1)

# =============================================================================
# CONFIGURAÇÃO E VARIÁVEIS DE AMBIENTE
# =============================================================================

# Carrega variáveis do ambiente do arquivo .env
load_dotenv()

# Configurações da Evolution API
evo_base_url = os.getenv("EVOLUTION_BASE_URL", "http://localhost:8080")  # URL base da Evolution API
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
    os.path.join(project_root, "crawler_qlik", "reports_qlik"),  # @reports_qlik/
    os.path.join(project_root, "crawler_qlik", "errorlogs"),    # @errorlogs/
    pasta_compartilhada  # Pasta compartilhada NPrinting
]

# =============================================================================
# VALIDAÇÃO DAS CONFIGURAÇÕES
# =============================================================================

# Verifica se todas as variáveis obrigatórias estão definidas
if not all([evo_api_token, evo_instance_id, evo_instance_token, (evo_grupo or evo_destino)]):
    print("❌ Variáveis de ambiente obrigatórias não definidas. Verifique o arquivo .env")
    print("📋 Variáveis necessárias:")
    print("   - EVOLUTION_API_TOKEN")
    print("   - EVOLUTION_INSTANCE_NAME") 
    print("   - EVOLUTION_INSTANCE_ID")
    print("   - EVO_DESTINO_GRUPO ou EVO_DESTINO")
    sys.exit(1)

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
    base_url=evo_base_url,
    api_token=evo_api_token
)

# =============================================================================
# COLETA DE DADOS DE STATUS
# =============================================================================

def executar_script_status(script_path, descricao):
    """
    Executa um script de status e captura sua saída.
    
    Args:
        script_path (str): Caminho para o script a ser executado
        descricao (str): Descrição do script para logs
        
    Returns:
        str: Saída do script ou mensagem de erro
    """
    try:
        print(f"🔄 Executando {descricao}...")
        
        # Configura ambiente com codificação UTF-8
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        env['PYTHONUTF8'] = '1'
        
        # Executa o script e captura a saída
        resultado = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',  # Substitui caracteres problemáticos
            cwd=project_root,
            env=env,
            timeout=300  # 5 minutos de timeout
        )
        
        if resultado.returncode == 0:
            print(f"✅ {descricao} executado com sucesso")
            # Verifica se stdout não é None antes de chamar strip()
            stdout_output = resultado.stdout.strip() if resultado.stdout else ""
            return stdout_output
        else:
            print(f"⚠️ {descricao} retornou código {resultado.returncode}")
            # Verifica se stderr não é None antes de chamar strip()
            stderr_output = resultado.stderr.strip() if resultado.stderr else "Erro desconhecido"
            return f"Erro na execução de {descricao}: {stderr_output}"
            
    except subprocess.TimeoutExpired:
        print(f"⏰ Timeout ao executar {descricao}")
        return f"Timeout ao executar {descricao}"
    except Exception as e:
        print(f"❌ Erro ao executar {descricao}: {e}")
        return f"Erro ao executar {descricao}: {str(e)}"

def coletar_resumos_status():
    """
    Coleta resumos de status do NPrinting, QMC, Desktop e ETL.
    
    Returns:
        dict: Dicionário com resumos organizados por categoria
    """
    try:
        resumos = {}
        
        # 1. Coleta status do NPrinting (relatórios)
        print("📊 Coletando status do NPrinting...")
        resumos_nprinting = coletar_status_nprinting()
        resumos['nprinting'] = resumos_nprinting
        
        # 2. Coleta status do QMC (estatísticas e painéis)
        print("📊 Coletando status do QMC...")
        resumos_qmc = coletar_status_qmc()
        resumos['qmc'] = resumos_qmc
        
        # 3. Coleta status do Qlik Sense Desktop
        print("🖥️ Coletando status do Qlik Sense Desktop...")
        script_desktop = os.path.join(project_root, "crawler_qlik", "status_qlik_desktop.py")
        if os.path.exists(script_desktop):
            resumo_desktop = executar_script_status(script_desktop, "Status Qlik Desktop")
            resumos['desktop'] = resumo_desktop
        else:
            print(f"⚠️ Script não encontrado: {script_desktop}")
            resumos['desktop'] = "Script de status do Desktop não encontrado"
        
        # 4. Coleta status das ETLs
        print("⚙️ Coletando status das ETLs...")
        script_etl = os.path.join(project_root, "crawler_qlik", "status_qlik_etl.py")
        if os.path.exists(script_etl):
            resumo_etl = executar_script_status(script_etl, "Status ETLs")
            resumos['etl'] = resumo_etl
        else:
            print(f"⚠️ Script não encontrado: {script_etl}")
            resumos['etl'] = "Script de status das ETLs não encontrado"
        
        return resumos
        
    except Exception as e:
        print(f"⚠️ Erro ao coletar resumos de status: {e}")
        return {
            'nprinting': {},
            'qmc': {},
            'desktop': f"Erro: {str(e)}",
            'etl': f"Erro: {str(e)}"
        }

def montar_resumo_concatenado(resumos):
    """
    Monta o resumo concatenado na ordem específica: relatórios, estatísticas, painéis, desktop, ETLs.
    
    Args:
        resumos (dict): Dicionário com resumos coletados
        
    Returns:
        str: Resumo concatenado em formato de texto
    """
    blocos = []
    
    # Ordem desejada: relatórios (NPrinting), estatísticas (QMC), painéis (QMC), desktop, ETLs
    if 'relatorios' in resumos.get('nprinting', {}):
        blocos.append("📊 **STATUS NPRINTING (RELATÓRIOS)**")
        blocos.append(resumos['nprinting']['relatorios'])
    
    if 'estatistica' in resumos.get('qmc', {}):
        blocos.append("📊 **STATUS QMC (ESTATÍSTICAS)**")
        blocos.append(resumos['qmc']['estatistica'])
    
    if 'paineis' in resumos.get('qmc', {}):
        blocos.append("📊 **STATUS QMC (PAINÉIS)**")
        blocos.append(resumos['qmc']['paineis'])
    
    if 'desktop' in resumos:
        blocos.append("🖥️ **STATUS QLIK SENSE DESKTOP**")
        blocos.append(resumos['desktop'])
    
    if 'etl' in resumos:
        blocos.append("⚙️ **STATUS ETLs**")
        blocos.append(resumos['etl'])
    
    if not blocos:
        return "Nenhum resumo de status disponível no momento."
    
    return "\n\n" + "\n\n".join(blocos)

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
        pasta_completa = os.path.join(project_root, "crawler_qlik", pasta)
        
        if not os.path.exists(pasta_completa):
            print(f"⚠️ Pasta não encontrada: {pasta_completa}")
            continue
            
        arquivos = [
            f for f in os.listdir(pasta_completa) 
            if f.endswith(".pdf") and f"_{sufixo}_" in f
        ]
        
        if not arquivos:
            print(f"📂 Nenhum arquivo PDF encontrado para {sufixo} em {pasta_completa}")
            continue
            
        # Pega o arquivo mais recente
        arquivos.sort(key=lambda n: os.path.getctime(os.path.join(pasta_completa, n)), reverse=True)
        arq = os.path.join(pasta_completa, arquivos[0])
        arquivos_pdf.append(arq)
        print(f"📄 Arquivo PDF encontrado para {sufixo}: {arquivos[0]}")
    
    # Envia cada arquivo PDF
    for arquivo in arquivos_pdf:
        enviar_para_todos_destinos(enviar_arquivo_para, arquivo)

# =============================================================================
# ENVIO DE LOGS DE ERRO
# =============================================================================

def enviar_logs_erro():
    """Envia logs de erro das ETLs para todos os destinos."""
    print("📋 Enviando logs de erro...")
    
    pasta_erro = os.path.join(project_root, "crawler_qlik", "errorlogs")
    
    if not os.path.exists(pasta_erro):
        print(f"⚠️ Pasta de logs de erro não encontrada: {pasta_erro}")
        return
    
    # Lista apenas arquivos .txt de erro
    arquivos_erro = [
        os.path.join(pasta_erro, f) 
        for f in os.listdir(pasta_erro) 
        if os.path.isfile(os.path.join(pasta_erro, f)) and f.endswith(('.txt', '.pdf'))
    ]
    
    if arquivos_erro:
        print(f"📋 Encontrados {len(arquivos_erro)} arquivos de erro")
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
    
    # Lista apenas arquivos .pdf da pasta compartilhada
    arquivos = [
        os.path.join(pasta_compartilhada, f) 
        for f in os.listdir(pasta_compartilhada) 
        if os.path.isfile(os.path.join(pasta_compartilhada, f)) and f.endswith(('.txt', '.pdf'))
    ]
    
    if not arquivos:
        print(f"📂 Nenhum relatório para enviar em: {pasta_compartilhada}")
        return
    
    print(f"📁 Encontrados {len(arquivos)} relatórios na pasta compartilhada")
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
    print(f"📁 Diretório do projeto: {project_root}")
    print(f"📁 Pasta de relatórios: {os.path.join(project_root, 'crawler_qlik', 'reports_qlik')}")
    print(f"📁 Pasta de logs de erro: {os.path.join(project_root, 'crawler_qlik', 'errorlogs')}")
    print(f"📁 Pasta compartilhada: {pasta_compartilhada}")
    
    # Configura credenciais de rede se disponíveis
    print("🌐 Configurando acesso de rede...")
    setup_network_credentials()
    
    try:
        # 1. Envia resumos de status (incluindo Desktop e ETLs)
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
