"""
Script para envio de relatórios e status Qlik via Evolution API
Executa scripts de status Qlik, coleta resumos e envia relatórios PDF e logs de erro
"""

import os
import sys
import shutil
import subprocess
import json
from datetime import datetime
from dotenv import load_dotenv

# Configuração UTF-8 para Windows
if os.name == 'nt':
    try:
        os.system('chcp 65001 > nul')
        # Reconfigura stdout para UTF-8
        sys.stdout.reconfigure(encoding='utf-8')
    except:
        pass

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
evo_base_url = os.getenv("EVOLUTION_BASE_URL", "http://localhost:8080")
evo_api_token = os.getenv("EVOLUTION_API_TOKEN")
evo_instance_id = os.getenv("EVOLUTION_INSTANCE_NAME")
evo_instance_token = os.getenv("EVOLUTION_INSTANCE_ID")
# Suporte a múltiplos destinos (separados por quebra de linha ou vírgula)
evo_grupo_raw = os.getenv("EVO_DESTINO_GRUPO", "")
evo_destino_raw = os.getenv("EVO_DESTINO", "")

# Processa múltiplos grupos (separa por quebras de linha ou vírgula)
evo_grupos = []
if evo_grupo_raw:
    # Remove comentários e separa por quebras de linha ou vírgula
    linhas = evo_grupo_raw.replace('\n', ',').split(',')
    for linha in linhas:
        linha = linha.strip().split('#')[0].strip()  # Remove comentários
        if linha and '@g.us' in linha:  # Só adiciona se for um grupo válido
            evo_grupos.append(linha)

# Processa múltiplos destinos individuais
evo_destinos = []
if evo_destino_raw:
    # Remove comentários e separa por quebras de linha ou vírgula
    linhas = evo_destino_raw.replace('\n', ',').split(',')
    for linha in linhas:
        linha = linha.strip().split('#')[0].strip()  # Remove comentários
        if linha and linha.isdigit():  # Só adiciona se for um número válido
            evo_destinos.append(linha)

# Mantém compatibilidade com versão anterior
evo_grupo = evo_grupos[0] if evo_grupos else ""
evo_destino = evo_destinos[0] if evo_destinos else ""

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
total_destinos = len(evo_grupos) + len(evo_destinos)
if not all([evo_api_token, evo_instance_id, evo_instance_token]) or total_destinos == 0:
    print("❌ Variáveis de ambiente obrigatórias não definidas. Verifique o arquivo .env")
    print("📋 Variáveis necessárias:")
    print("   - EVOLUTION_API_TOKEN")
    print("   - EVOLUTION_INSTANCE_NAME") 
    print("   - EVOLUTION_INSTANCE_ID")
    print("   - EVO_DESTINO_GRUPO ou EVO_DESTINO")
    print(f"📊 Destinos encontrados: {total_destinos}")
    print(f"   Grupos: {len(evo_grupos)}")
    print(f"   Destinos individuais: {len(evo_destinos)}")
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
# FUNÇÕES DE NORMALIZAÇÃO E UTILITÁRIOS
# =============================================================================

def to_whatsapp_jid(raw_number: str) -> str:
    """
    Normaliza número de telefone para formato JID do WhatsApp (E.164).
    
    Args:
        raw_number (str): Número bruto (pode ter formatação)
        
    Returns:
        str: JID no formato correto (ex: 5562981613538@s.whatsapp.net)
        
    Raises:
        ValueError: Se o número for inválido
    """
    import re
    
    # Remove caracteres não numéricos
    digits = re.sub(r'\D+', '', str(raw_number or ''))
    
    if not digits:
        raise ValueError("Número vazio")
    
    # Se já vier com DDI do Brasil
    if digits.startswith('55'):
        pass
    # Se vier sem DDI mas parecer BR (10 ou 11 dígitos: DDD + local)
    elif len(digits) in (10, 11):
        digits = '55' + digits
    # Caso contrário, trate como E.164 de outro país (não force 55)
    # apenas siga com 'digits' como está
    
    # Validação E.164 (até 15 dígitos)
    if not (8 <= len(digits) <= 15):
        raise ValueError(f"Número fora do padrão E.164: {digits} (deve ter 8-15 dígitos)")
    
    # Log para debug
    print(f"🔢 Normalização E.164: {raw_number} → {digits}@s.whatsapp.net")
    
    return f"{digits}@s.whatsapp.net"

def is_session_error(response):
    """
    Verifica se a resposta contém erro de sessão.
    
    Args:
        response: Resposta da API
        
    Returns:
        bool: True se for erro de sessão
    """
    if isinstance(response, dict):
        if response.get('status') == 400:
            error_msg = str(response.get('response', {}).get('message', []))
            return 'SessionError: No sessions' in error_msg
    return False

def warmup_group_session(group_jid, warmup_text="⏳ Preparando envio de relatórios..."):
    """
    Aquece a sessão do grupo enviando uma mensagem de texto.
    
    Args:
        group_jid (str): JID do grupo
        warmup_text (str): Texto de aquecimento
        
    Returns:
        bool: True se o aquecimento foi bem-sucedido
    """
    try:
        print(f"🔥 Aquecendo sessão do grupo: {group_jid}")
        
        # Envia mensagem de aquecimento
        client.messages.send_text(
            evo_instance_id,
            TextMessage(
                number=group_jid,
                text=warmup_text
            ),
            evo_instance_token
        )
        
        # Aguarda um pouco para a sessão se estabilizar
        import time
        time.sleep(3)
        
        print(f"✅ Sessão do grupo aquecida: {group_jid}")
        return True
        
    except Exception as e:
        print(f"⚠️ Erro no aquecimento do grupo {group_jid}: {e}")
        return False

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

def enviar_arquivo_para(destinatario, caminho_completo, max_retries=3):
    """
    Envia um arquivo para um destinatário específico via Evolution API.
    
    Args:
        destinatario (str): Número ou ID do destinatário
        caminho_completo (str): Caminho completo do arquivo a ser enviado
        max_retries (int): Número máximo de tentativas para grupos
    """
    import time
    
    nome_arquivo = os.path.basename(caminho_completo)
    ext = os.path.splitext(nome_arquivo)[1].lower()
    
    # Normaliza o destinatário
    try:
        if destinatario.endswith('@g.us'):
            # É um grupo - não normaliza
            jid_final = destinatario
        else:
            # É um número individual - normaliza
            jid_final = to_whatsapp_jid(destinatario)
    except ValueError as e:
        print(f"❌ Erro na normalização do número {destinatario}: {e}")
        return False
    
    # Mapeamento completo de extensões para MIME e MediaType
    extmap = {
        ".pdf": ("application/pdf", "document"),
        ".json": ("application/json", "document"),
        ".txt": ("text/plain", "document"),
        ".png": ("image/png", "image"),
        ".jpg": ("image/jpeg", "image"),
        ".jpeg": ("image/jpeg", "image"),
        ".gif": ("image/gif", "image"),
        ".webp": ("image/webp", "image"),
    }
    
    mimetype, mediatype = extmap.get(ext, ("application/octet-stream", "document"))
    
    # Cria mensagem de mídia
    media_message = MediaMessage(
        number=jid_final,
        mediatype=mediatype,
        mimetype=mimetype,
        caption=f"📎 {nome_arquivo}",
        fileName=nome_arquivo
    )
    
    # Se for grupo, aquece a sessão primeiro
    if jid_final.endswith('@g.us'):
        warmup_group_session(jid_final)
    
    # Tenta enviar com retry para grupos
    for attempt in range(max_retries if jid_final.endswith('@g.us') else 1):
        try:
            # Envia o arquivo via Evolution API
            response = client.messages.send_media(
                evo_instance_id,
                media_message,
                evo_instance_token,
                caminho_completo
            )
            
            # Verifica se houve erro de sessão
            if is_session_error(response):
                if attempt < max_retries - 1:
                    print(f"⚠️ SessionError no grupo {jid_final}, tentativa {attempt + 1}/{max_retries}")
                    time.sleep(8)  # Aguarda mais tempo para a sessão se estabilizar
                    continue
                else:
                    print(f"❌ Falha após {max_retries} tentativas no grupo {jid_final}")
                    return False
            
            print(f"📨 Enviado para {jid_final}: {nome_arquivo} | Resultado: {response}")
            
            # Log detalhado para debug
            if isinstance(response, dict) and 'key' in response:
                message_id = response['key'].get('id', 'N/A')
                print(f"🔍 Debug - Message ID: {message_id}, JID: {jid_final}")
            
            return True
            
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"⚠️ Erro na tentativa {attempt + 1}/{max_retries}: {e}")
                time.sleep(5)
            else:
                print(f"❌ Erro ao enviar arquivo {nome_arquivo} para {jid_final}: {e}")
                return False
    
    return False

def enviar_mensagem_texto(destinatario, texto):
    """
    Envia uma mensagem de texto para um destinatário específico.
    
    Args:
        destinatario (str): Número ou ID do destinatário
        texto (str): Texto da mensagem a ser enviada
    """
    # Normaliza o destinatário
    try:
        if destinatario.endswith('@g.us'):
            # É um grupo - não normaliza
            jid_final = destinatario
        else:
            # É um número individual - normaliza
            jid_final = to_whatsapp_jid(destinatario)
    except ValueError as e:
        print(f"❌ Erro na normalização do número {destinatario}: {e}")
        return False
    
    try:
        client.messages.send_text(
            evo_instance_id,
            TextMessage(
                number=jid_final,
                text=texto
            ),
            evo_instance_token
        )
        print(f"✅ Mensagem de texto enviada para: {jid_final}")
        return True
    except Exception as e:
        import traceback
        print(f"❌ Erro ao enviar mensagem de texto para {jid_final}: {e}")
        print(f"🔍 Traceback: {traceback.format_exc()}")
        return False

def enviar_para_todos_destinos(func, *args, **kwargs):
    """
    Executa uma função para todos os destinos configurados.
    
    Args:
        func: Função a ser executada
        *args: Argumentos posicionais para a função
        **kwargs: Argumentos nomeados para a função
        
    Returns:
        dict: Estatísticas de envio {'sucessos': int, 'falhas': int, 'total': int}
    """
    # Combina todos os destinos (grupos + individuais)
    todos_destinos = evo_destinos + evo_grupos
    
    print(f"📤 Enviando para {len(todos_destinos)} destino(s):")
    for i, destino in enumerate(todos_destinos, 1):
        print(f"   {i}. {destino}")
    
    sucessos = 0
    falhas = 0
    
    for destino in todos_destinos:
        if not destino:
            print(f"⚠️ Destino não definido: {destino}")
            falhas += 1
            continue
        
        try:
            resultado = func(destino, *args, **kwargs)
            if resultado is not False:  # Se a função retornou True ou None (sucesso)
                sucessos += 1
            else:
                falhas += 1
        except Exception as e:
            print(f"❌ Erro ao processar destino {destino}: {e}")
            falhas += 1
    
    estatisticas = {
        'sucessos': sucessos,
        'falhas': falhas,
        'total': len(todos_destinos)
    }
    
    print(f"📊 Estatísticas: {sucessos} sucessos, {falhas} falhas de {len(todos_destinos)} destinos")
    return estatisticas

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
    stats_resumos = enviar_para_todos_destinos(enviar_mensagem_texto, resumo_concat)
    return stats_resumos

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
    stats_pdfs = {'sucessos': 0, 'falhas': 0, 'total': 0}
    for arquivo in arquivos_pdf:
        stats_arquivo = enviar_para_todos_destinos(enviar_arquivo_para, arquivo)
        # Acumula estatísticas
        stats_pdfs['sucessos'] += stats_arquivo['sucessos']
        stats_pdfs['falhas'] += stats_arquivo['falhas']
        stats_pdfs['total'] += stats_arquivo['total']
    
    return stats_pdfs

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
        stats_erros = {'sucessos': 0, 'falhas': 0, 'total': 0}
        for arquivo in arquivos_erro:
            stats_arquivo = enviar_para_todos_destinos(enviar_arquivo_para, arquivo)
            stats_erros['sucessos'] += stats_arquivo['sucessos']
            stats_erros['falhas'] += stats_arquivo['falhas']
            stats_erros['total'] += stats_arquivo['total']
        return stats_erros
    else:
        # Envia mensagem de que não há erros
        mensagem = "✅ Nenhum erro encontrado nas ETLs."
        stats_erros = enviar_para_todos_destinos(enviar_mensagem_texto, mensagem)
        return stats_erros

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
    stats_compartilhados = {'sucessos': 0, 'falhas': 0, 'total': 0}
    for arquivo in arquivos:
        stats_arquivo = enviar_para_todos_destinos(enviar_arquivo_para, arquivo)
        stats_compartilhados['sucessos'] += stats_arquivo['sucessos']
        stats_compartilhados['falhas'] += stats_arquivo['falhas']
        stats_compartilhados['total'] += stats_arquivo['total']
    
    return stats_compartilhados

# =============================================================================
# LIMPEZA DAS PASTAS APÓS ENVIO
# =============================================================================

def limpar_pastas_apos_envio():
    """Limpa as pastas após o envio bem-sucedido dos arquivos, preservando arquivos .gitkeep."""
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
        
        # Remove apenas arquivos que não são .gitkeep
        arquivos_removidos = 0
        for arquivo in arquivos:
            nome_arquivo = os.path.basename(arquivo)
            
            # Preserva arquivos .gitkeep para manter estrutura do Git
            if nome_arquivo == '.gitkeep':
                print(f"💾 Preservando arquivo .gitkeep: {nome_arquivo}")
                continue
            
            try:
                os.remove(arquivo)
                print(f"🗑️ Arquivo removido: {nome_arquivo}")
                arquivos_removidos += 1
            except Exception as e:
                print(f"❌ Erro ao remover {arquivo}: {e}")
        
        print(f"🧹 Pasta limpa: {pasta} ({arquivos_removidos} arquivos removidos)")

# =============================================================================
# FUNÇÃO PRINCIPAL
# =============================================================================

def main():
    """Função principal que executa todo o fluxo de envio Qlik."""
    print("🚀 Iniciando processo de envio Qlik via Evolution API...")
    print(f"📁 Diretório do projeto: {project_root}")
    print(f"📁 Pasta de relatórios: {os.path.join(project_root, 'crawler_qlik', 'reports_qlik')}")
    print(f"📁 Pasta de logs de erro: {os.path.join(project_root, 'crawler_qlik', 'errorlogs')}")
    print(f"📁 Pasta compartilhada: {pasta_compartilhada}")
    
    # Debug: mostra destinos carregados
    print(f"\n📊 DESTINOS CONFIGURADOS:")
    print(f"   📱 Destinos individuais ({len(evo_destinos)}):")
    for i, destino in enumerate(evo_destinos, 1):
        print(f"      {i}. {destino}")
    print(f"   👥 Grupos ({len(evo_grupos)}):")
    for i, grupo in enumerate(evo_grupos, 1):
        print(f"      {i}. {grupo}")
    print(f"   📊 Total de destinos: {len(evo_destinos) + len(evo_grupos)}")
    
    # Configura credenciais de rede se disponíveis
    print("\n🌐 Configurando acesso de rede...")
    setup_network_credentials()
    
    try:
        print("\n" + "="*60)
        print("📊 ENVIO DE RESUMOS DE STATUS")
        print("="*60)
        try:
            stats_resumos = enviar_resumos_status()
        except KeyboardInterrupt:
            print("⚠️ Envio interrompido - continuando...")
            stats_resumos = {'sucessos': 0, 'falhas': 1, 'total': 1}
        
        print("\n" + "="*60)
        print("📄 ENVIO DE ARQUIVOS PDF DE STATUS")
        print("="*60)
        try:
            stats_pdfs = enviar_pdfs_status()
        except KeyboardInterrupt:
            print("⚠️ Envio interrompido - continuando...")
            stats_pdfs = {'sucessos': 0, 'falhas': 1, 'total': 1}
        
        print("\n" + "="*60)
        print("📋 ENVIO DE LOGS DE ERRO")
        print("="*60)
        try:
            stats_erros = enviar_logs_erro()
        except KeyboardInterrupt:
            print("⚠️ Envio interrompido - continuando...")
            stats_erros = {'sucessos': 0, 'falhas': 1, 'total': 1}
        
        print("\n" + "="*60)
        print("📁 ENVIO DE RELATÓRIOS COMPARTILHADOS")
        print("="*60)
        try:
            stats_compartilhados = enviar_relatorios_compartilhados()
        except KeyboardInterrupt:
            print("⚠️ Envio interrompido - continuando...")
            stats_compartilhados = {'sucessos': 0, 'falhas': 1, 'total': 1}
        
        # Calcula estatísticas totais
        total_sucessos = (stats_resumos.get('sucessos', 0) + 
                         stats_pdfs.get('sucessos', 0) + 
                         stats_erros.get('sucessos', 0) +
                         stats_compartilhados.get('sucessos', 0))
        total_falhas = (stats_resumos.get('falhas', 0) + 
                       stats_pdfs.get('falhas', 0) + 
                       stats_erros.get('falhas', 0) +
                       stats_compartilhados.get('falhas', 0))
        
        print(f"\n📊 ESTATÍSTICAS FINAIS:")
        print(f"   ✅ Sucessos: {total_sucessos}")
        print(f"   ❌ Falhas: {total_falhas}")
        print(f"   📊 Total: {total_sucessos + total_falhas}")
        
        # Limpeza condicional - só limpa se houve sucessos
        if total_sucessos > 0:
            print("\n" + "="*60)
            print("🧹 LIMPEZA DAS PASTAS")
            print("="*60)
            try:
                limpar_pastas_apos_envio()
            except KeyboardInterrupt:
                print("⚠️ Limpeza interrompida - continuando...")
        else:
            print("\n⚠️ Nenhum envio bem-sucedido - mantendo arquivos para reenvio")
        
        if total_falhas == 0:
            print("\n✅ Processo Qlik finalizado com sucesso!")
        else:
            print(f"\n⚠️ Processo Qlik finalizado com {total_falhas} falha(s)")
        
    except KeyboardInterrupt:
        print("\n⚠️ Processo interrompido pelo usuário")
        try:
            enviar_logs_erro()
        except:
            pass
        print("✅ Processo finalizado")
        
    except Exception as e:
        print(f"\n❌ Erro: {e}")
        print("🔄 Continuando...")

# =============================================================================
# EXECUÇÃO DO SCRIPT
# =============================================================================

if __name__ == "__main__":
    main()
