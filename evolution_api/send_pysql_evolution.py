"""
Script para envio de relatórios PySQL via Evolution API
Executa scripts PySQL, coleta resumos de tempos de consulta e envia relatórios PDF e logs de erro
"""

import os
import sys
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
except ImportError as e:
    print(f"❌ Erro ao importar módulos: {e}")
    print("💡 Certifique-se de que todas as dependências estão instaladas:")
    print("   pip install python-dotenv evolution-api")
    sys.exit(1)

# =============================================================================
# CONFIGURAÇÃO E VARIÁVEIS DE AMBIENTE
# =============================================================================

# Carrega .env da raiz do projeto (necessário para subprocess dos scripts pysql: ORACLE_*, GITLAB_*, etc.)
load_dotenv(os.path.join(project_root, ".env"))
load_dotenv()  # Sobrescreve com .env local do evolution_api se existir

# Configurações da Evolution API (URL resolvida por validação: localhost → hostname → IP)
evo_base_url_raw = os.getenv("EVOLUTION_BASE_URL", "http://localhost:8080")
evo_api_token = os.getenv("EVOLUTION_API_TOKEN")
evo_instance_id = os.getenv("EVOLUTION_INSTANCE_NAME")
evo_instance_token = os.getenv("EVOLUTION_INSTANCE_ID")
# Suporte a múltiplos destinos (separados por quebra de linha ou vírgula)
evo_grupo_raw = os.getenv("EVO_DESTINO_GRUPO", "")
evo_destino_raw = os.getenv("EVO_DESTINO", "")
# Grupo administrativo para notificação de erros (ex.: BI SSP)
evo_grupo_admin = (os.getenv("EVO_GRUPO_ADMIN", "") or "").strip()
if evo_grupo_admin and "@g.us" not in evo_grupo_admin:
    evo_grupo_admin = ""

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

# Diretórios PySQL
reports_pysql_dir = os.path.join(project_root, "pysql", "reports_pysql")
errorlogs_pysql_dir = os.path.join(project_root, "pysql", "errorlogs")
img_reports_dir = os.path.join(project_root, "pysql", "img_reports")
pysql_dir = os.path.join(project_root, "pysql")

# Lista de pastas para envio
pastas_envio = [reports_pysql_dir, errorlogs_pysql_dir, img_reports_dir]

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
# VALIDAÇÃO DA URL DA EVOLUTION API (localhost → hostname → IP)
# =============================================================================

def _testar_url_evolution(base_url: str, timeout: int = 5) -> bool:
    """Testa se a Evolution API responde na URL (qualquer resposta = servidor acessível)."""
    try:
        import requests
        url = base_url.rstrip("/")
        requests.get(url, timeout=timeout)
        return True
    except Exception:
        return False


def _resolver_evolution_base_url() -> str:
    """
    Tenta em ordem: URL do .env → localhost → URLs em EVOLUTION_FALLBACK_URLS (.env).
    Não expõe IPs/hosts no código; fallback explícito apenas localhost.
    """
    candidatos = [
        evo_base_url_raw.strip().rstrip("/"),
        "http://localhost:8080",
    ]
    fallback_raw = os.getenv("EVOLUTION_FALLBACK_URLS", "").strip()
    if fallback_raw:
        for u in fallback_raw.replace(",", " ").split():
            u = u.strip().rstrip("/")
            if u and u not in candidatos:
                candidatos.append(u)
    for url in candidatos:
        if _testar_url_evolution(url):
            return url
    return evo_base_url_raw.strip().rstrip("/")


evo_base_url = _resolver_evolution_base_url()
# Não expor URL (exceto localhost)
if "localhost" in evo_base_url:
    print("🔗 Evolution API: OK (localhost)", flush=True)
else:
    print("🔗 Evolution API: OK", flush=True)

# =============================================================================
# INICIALIZAÇÃO DO CLIENTE EVOLUTION
# =============================================================================

# Inicializa o cliente da Evolution API
client = EvolutionClient(
    base_url=evo_base_url,
    api_token=evo_api_token
)

# =============================================================================
# VERIFICAÇÃO DE DEPENDÊNCIAS
# =============================================================================

def verificar_dependencias_pysql():
    """Verifica dependências PySQL."""
    print("🔍 Verificando dependências PySQL...")
    
    dependencias = ['oracledb', 'pandas', 'matplotlib', 'seaborn', 'fpdf', 'tqdm']
    faltando = []
    
    for dep in dependencias:
        try:
            __import__(dep)
            print(f"   ✅ {dep}")
        except ImportError:
            print(f"   ❌ {dep}")
            faltando.append(dep)
    
    if faltando:
        print(f"⚠️ Faltando: {', '.join(faltando)}")
        return False
    
    print("✅ Todas as dependências disponíveis")
    return True

# =============================================================================
# EXECUÇÃO DE SCRIPTS PYSQL
# =============================================================================





def executar_scripts_pysql():
    """
    Executa todos os scripts Python encontrados na pasta pysql/.
    
    Returns:
        dict: Dicionário com resultados da execução de cada script
    """
    print("🚀 Executando scripts PySQL...")
    
    resultados = {}
    
    if not os.path.exists(pysql_dir):
        print(f"⚠️ Pasta PySQL não encontrada: {pysql_dir}")
        return resultados
    
    # Lista apenas scripts de relatório (filtro por prefixo)
    scripts_python = [
        f for f in os.listdir(pysql_dir) 
        if f.endswith('.py') and f != '__init__.py' and f.startswith(('pysql_', 'report_'))
    ]
    
    if not scripts_python:
        print(f"📂 Nenhum script Python encontrado em {pysql_dir}")
        return resultados
    
    print(f"📄 Encontrados {len(scripts_python)} scripts Python")
    
    # Executa cada script usando a mesma lógica da função de teste que funciona
    for i, script in enumerate(scripts_python, 1):
        script_path = os.path.join(pysql_dir, script)
        descricao = f"Script {script}"
        
        print(f"\n{'='*60}")
        print(f"🔄 EXECUTANDO SCRIPT {i}/{len(scripts_python)}: {script}")
        print(f"{'='*60}")
        
        try:
            print(f"🚀 Executando {descricao}...")
            print(f"   📁 Script: {script_path}")
            
            env = os.environ.copy()
            env['PYTHONIOENCODING'] = 'utf-8'
            env['PYTHONUTF8'] = '1'
            
            try:
                resultado = subprocess.run(
                    [sys.executable, script_path],
                    capture_output=False,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                    cwd=project_root,
                    env=env,
                    timeout=60*60*3  # 3 horas timeout (10800 segundos)
                )
                
                if resultado.returncode == 0:
                    print(f"✅ {descricao} executado com sucesso")
                    resultados[script] = f"Script {descricao} executado com sucesso (código {resultado.returncode})"
                else:
                    print(f"⚠️ {descricao} retornou código {resultado.returncode}")
                    resultados[script] = f"Erro na execução de {descricao} (código {resultado.returncode})"
                    
            except KeyboardInterrupt:
                print(f"⚠️ {descricao} foi interrompido pelo usuário - continuando...")
                resultados[script] = f"Script {descricao} foi interrompido pelo usuário"
                # Continua para o próximo script em vez de parar
                continue
                
        except subprocess.TimeoutExpired:
            print(f"⏰ Timeout ao executar {descricao} (3 horas)")
            resultados[script] = f"Timeout ao executar {descricao} (3 horas)"
        except Exception as e:
            import traceback
            print(f"❌ Erro ao executar {descricao}: {e}")
            print(f"🔍 Traceback: {traceback.format_exc()}")
            resultados[script] = f"Erro ao executar {descricao}: {str(e)}"
        
        # Aguarda um pouco entre execuções para não sobrecarregar
        if i < len(scripts_python):  # Não aguarda após o último script
            print(f"⏳ Aguardando 3 segundos antes do próximo script...")
            import time
            time.sleep(3)
    
    return resultados

# =============================================================================
# ANÁLISE DE TEMPOS DE EXECUÇÃO
# =============================================================================

def analisar_tempos_execucao():
    """
    Analisa os arquivos JSON de tempos de execução e gera resumos.
    
    Returns:
        dict: Dicionário com resumos de tempos organizados por script
    """
    print("📊 Analisando tempos de execução...")
    
    resumos = {}
    
    if not os.path.exists(reports_pysql_dir):
        print(f"⚠️ Pasta de relatórios não encontrada: {reports_pysql_dir}")
        return resumos
    
    # Busca arquivos JSON de tempos de execução
    arquivos_json = [
        f for f in os.listdir(reports_pysql_dir) 
        if f.endswith('_tempos_execucao.json')
    ]
    
    if not arquivos_json:
        print(f"📂 Nenhum arquivo de tempos de execução encontrado")
        return resumos
    
    print(f"📄 Encontrados {len(arquivos_json)} arquivos de tempos de execução")
    
    # Analisa cada arquivo JSON
    for arquivo_json in arquivos_json:
        try:
            caminho_completo = os.path.join(reports_pysql_dir, arquivo_json)
            
            with open(caminho_completo, 'r', encoding='utf-8') as f:
                dados = json.load(f)
            
            # Extrai o nome do script do nome do arquivo
            nome_script = arquivo_json.replace('_tempos_execucao.json', '')
            
            # Gera resumo dos tempos
            resumo = gerar_resumo_tempos(dados, nome_script)
            resumos[nome_script] = resumo
            
        except Exception as e:
            print(f"❌ Erro ao analisar {arquivo_json}: {e}")
            resumos[arquivo_json.replace('_tempos_execucao.json', '')] = f"Erro na análise: {str(e)}"
    
    return resumos

def formatar_duracao(segundos):
    """Converte segundos em formato legível: Xs, X min ou Xh Y min."""
    if segundos < 60:
        return f"{segundos:.0f}s"
    if segundos < 3600:
        m = segundos / 60
        return f"{m:.0f} min" if m == int(m) else f"{m:.1f} min"
    h = int(segundos // 3600)
    m = (segundos % 3600) / 60
    if m < 1:
        return f"{h}h"
    return f"{h}h {m:.0f} min"


def gerar_resumo_tempos(dados, nome_script):
    """
    Gera um resumo curto: script, última execução e tempo total (em min/h).
    """
    try:
        if not dados:
            return f"Nenhum dado para {nome_script}"
        timestamps = sorted(dados.keys(), reverse=True)
        if not timestamps:
            return f"Nenhum timestamp para {nome_script}"
        execucao_recente = dados[timestamps[0]]
        tempo_total = sum(execucao_recente.values())
        resumo = f"📊 **{nome_script.upper()}**\n"
        resumo += f"Última execução: {timestamps[0][:19].replace('T', ' ')}\n"
        resumo += f"Tempo total: {formatar_duracao(tempo_total)}\n"
        return resumo
    except Exception as e:
        return f"Erro ao gerar resumo para {nome_script}: {str(e)}"

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
        print("🔥 Aquecendo sessão do grupo...")
        
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
        
        print("✅ Sessão do grupo aquecida")
        return True
        
    except Exception as e:
        print(f"⚠️ Erro no aquecimento do grupo: {e}")
        return False

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
                    print(f"⚠️ SessionError no grupo, tentativa {attempt + 1}/{max_retries}")
                    time.sleep(8)  # Aguarda mais tempo para a sessão se estabilizar
                    continue
                else:
                    print(f"❌ Falha após {max_retries} tentativas no grupo")
                    return False
            
            print(f"📨 Enviado: {nome_arquivo}")
            
            
            return True
            
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"⚠️ Erro na tentativa {attempt + 1}/{max_retries}: {e}")
                time.sleep(5)
            else:
                print(f"❌ Erro ao enviar arquivo {nome_arquivo}: {e}")
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
        if destinatario == evo_grupo_admin:
            print("✅ Notificação enviada ao grupo administrativo", flush=True)
        else:
            print("✅ Mensagem de texto enviada")
        return True
    except Exception as e:
        import traceback
        if destinatario == evo_grupo_admin:
            print("❌ Erro ao enviar notificação ao grupo administrativo", flush=True)
        else:
            print(f"❌ Erro ao enviar mensagem de texto: {e}")
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
    
    print(f"📤 Enviando para {len(todos_destinos)} destino(s)")
    
    sucessos = 0
    falhas = 0
    
    for destino in todos_destinos:
        if not destino:
            print("⚠️ Destino não definido")
            falhas += 1
            continue
        
        try:
            resultado = func(destino, *args, **kwargs)
            if resultado is not False:  # Se a função retornou True ou None (sucesso)
                sucessos += 1
            else:
                falhas += 1
        except Exception as e:
            print(f"❌ Erro ao processar destino: {e}")
            falhas += 1
    
    estatisticas = {
        'sucessos': sucessos,
        'falhas': falhas,
        'total': len(todos_destinos)
    }
    
    print(f"📊 Estatísticas: {sucessos} sucessos, {falhas} falhas de {len(todos_destinos)} destinos")
    return estatisticas


def notificar_erro_admin(mensagem_erro: str) -> bool:
    """Envia mensagem de erro ao grupo administrativo (EVO_GRUPO_ADMIN), sem expor dados sensíveis."""
    if not evo_grupo_admin:
        return False
    try:
        return enviar_mensagem_texto(evo_grupo_admin, mensagem_erro)
    except Exception:
        return False


# =============================================================================
# ENVIO DE RESUMOS DE TEMPOS
# =============================================================================

def enviar_resumos_tempo():
    """Envia resumos de tempos de execução para todos os destinos."""
    print("📊 Enviando resumos de tempos de execução...")
    
    # Tempo sem intercorrências (histórico de envio/execução)
    try:
        from pysql.historico_pysql_evolution import texto_tempo_sem_intercorrencias
        linha_intercorrencias = texto_tempo_sem_intercorrencias()
    except Exception:
        linha_intercorrencias = "Tempo sem intercorrências: (histórico indisponível)"
    
    # Analisa os tempos de execução
    resumos = analisar_tempos_execucao()
    
    if not resumos:
        mensagem = "Nenhum resumo de tempo de execução disponível no momento.\n\n" + linha_intercorrencias
        enviar_para_todos_destinos(enviar_mensagem_texto, mensagem)
        return
    
    # Monta o resumo concatenado (resumido: cabeçalho, tempo sem intercorrências, script, execução, tempo)
    resumo_concat = "⏱️ **RESUMOS DE TEMPOS DE EXECUÇÃO PYSQL**\n\n"
    resumo_concat += f"🟢 {linha_intercorrencias}\n\n"
    for nome_script, resumo in resumos.items():
        resumo_concat += resumo + "\n\n"
    
    # Envia para todos os destinos
    stats_resumos = enviar_para_todos_destinos(enviar_mensagem_texto, resumo_concat)
    return stats_resumos

# =============================================================================
# ENVIO DE RELATÓRIOS PDF
# =============================================================================

def enviar_relatorios_pdf():
    """Envia relatórios PDF das consultas PySQL."""
    print("📄 Enviando relatórios PDF...")
    
    if not os.path.exists(reports_pysql_dir):
        print(f"⚠️ Pasta de relatórios não encontrada: {reports_pysql_dir}")
        return
    
    # Busca apenas arquivos PDF
    arquivos_pdf = [
        f for f in os.listdir(reports_pysql_dir) 
        if f.endswith(".pdf")
    ]
    
    if not arquivos_pdf:
        print(f"📂 Nenhum relatório PDF encontrado em {reports_pysql_dir}")
        return
    
    print(f"📄 Encontrados {len(arquivos_pdf)} relatórios PDF")
    
    # Envia cada arquivo PDF
    stats_pdfs = {'sucessos': 0, 'falhas': 0, 'total': 0}
    
    for arquivo in arquivos_pdf:
        caminho_completo = os.path.join(reports_pysql_dir, arquivo)
        print(f"📤 Enviando: {arquivo}")
        stats_arquivo = enviar_para_todos_destinos(enviar_arquivo_para, caminho_completo)
        
        # Acumula estatísticas
        stats_pdfs['sucessos'] += stats_arquivo['sucessos']
        stats_pdfs['falhas'] += stats_arquivo['falhas']
        stats_pdfs['total'] += stats_arquivo['total']
    
    return stats_pdfs



# =============================================================================
# ENVIO DE LOGS DE ERRO
# =============================================================================

def enviar_logs_erro():
    """Envia logs de erro das consultas PySQL."""
    print("📋 Enviando logs de erro...")
    
    if not os.path.exists(errorlogs_pysql_dir):
        print(f"⚠️ Pasta de logs de erro não encontrada: {errorlogs_pysql_dir}")
        return
    
    # Lista apenas arquivos .txt e .pdf de erro
    arquivos_erro = [
        os.path.join(errorlogs_pysql_dir, f) 
        for f in os.listdir(errorlogs_pysql_dir) 
        if os.path.isfile(os.path.join(errorlogs_pysql_dir, f)) and f.endswith(('.txt', '.pdf'))
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
        mensagem = "✅ Nenhum erro encontrado nas consultas PySQL."
        stats_erros = enviar_para_todos_destinos(enviar_mensagem_texto, mensagem)
        return stats_erros

# =============================================================================
# LIMPEZA DAS PASTAS APÓS ENVIO
# =============================================================================

def limpar_pastas_apos_envio():
    """Limpa as pastas após o envio bem-sucedido dos arquivos, preservando arquivos JSON."""
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
        
        # Remove apenas arquivos que não são JSON (para preservar histórico), .gitkeep e LogoRelatorio.jpg
        arquivos_removidos = 0
        for arquivo in arquivos:
            nome_arquivo = os.path.basename(arquivo)
            
            # Preserva arquivos JSON para manter série histórica
            if nome_arquivo.endswith('.json'):
                print(f"💾 Preservando arquivo histórico: {nome_arquivo}")
                continue
            
            # Preserva arquivos .gitkeep para manter estrutura do Git
            if nome_arquivo == '.gitkeep':
                print(f"💾 Preservando arquivo .gitkeep: {nome_arquivo}")
                continue
            
            # Preserva o arquivo LogoRelatorio.jpg
            if nome_arquivo == 'LogoRelatorio.jpg':
                print(f"💾 Preservando logo do relatório: {nome_arquivo}")
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
    """Função principal que executa todo o fluxo de envio PySQL."""
    print("🚀 Iniciando processo de envio PySQL via Evolution API...")
    print(f"📁 Diretório do projeto: {project_root}")
    print(f"📁 Pasta de relatórios PySQL: {reports_pysql_dir}")
    print(f"📁 Pasta de logs de erro PySQL: {errorlogs_pysql_dir}")
    print(f"📁 Pasta de scripts PySQL: {pysql_dir}")
    
    print(f"\n📊 Destinos: {len(evo_destinos) + len(evo_grupos)} configurado(s)")
    
    try:
        print("\n" + "="*60)
        print("🔍 VERIFICAÇÃO DE DEPENDÊNCIAS PYSQL")
        print("="*60)
        verificar_dependencias_pysql()

        print("\n" + "="*60)
        print("🔄 EXECUÇÃO DE SCRIPTS PYSQL")
        print("="*60)
        try:
            resultados_execucao = executar_scripts_pysql()
        except KeyboardInterrupt:
            print("⚠️ Execução interrompida - continuando...")
            resultados_execucao = {"interrompido": "Execução interrompida"}
        
        print("\n" + "="*60)
        print("📊 ENVIO DE RESUMOS DE TEMPOS")
        print("="*60)
        try:
            stats_resumos = enviar_resumos_tempo()
        except KeyboardInterrupt:
            print("⚠️ Envio interrompido - continuando...")
            stats_resumos = {'sucessos': 0, 'falhas': 1, 'total': 1}
        
        print("\n" + "="*60)
        print("📄 ENVIO DE RELATÓRIOS PDF")
        print("="*60)
        try:
            stats_pdfs = enviar_relatorios_pdf()
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
        
        # Calcula estatísticas totais (stats_* podem ser None se pasta não existir)
        total_sucessos = ((stats_resumos or {}).get('sucessos', 0) +
                         (stats_pdfs or {}).get('sucessos', 0) +
                         (stats_erros or {}).get('sucessos', 0))
        total_falhas = ((stats_resumos or {}).get('falhas', 0) +
                       (stats_pdfs or {}).get('falhas', 0) +
                       (stats_erros or {}).get('falhas', 0))
        
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
            print("\n✅ Processo PySQL finalizado com sucesso!")
        else:
            print(f"\n⚠️ Processo PySQL finalizado com {total_falhas} falha(s)")

        # Nenhum envio bem-sucedido = falha: notifica admin e sai com código 1 (histórico marca erro)
        if total_sucessos == 0:
            msg = "⚠️ *PySQL + Evolution*: falha no envio. Nenhuma mensagem entregue aos destinos. Verifique conexão e logs."
            notificar_erro_admin(msg)
            sys.exit(1)
        
    except KeyboardInterrupt:
        print("\n⚠️ Processo interrompido pelo usuário")
        try:
            enviar_logs_erro()
        except:
            pass
        print("✅ Processo finalizado")
        
    except Exception as e:
        print(f"\n❌ Erro: {e}")
        msg = f"⚠️ *PySQL + Evolution*: erro na execução. {str(e)[:200]}"
        notificar_erro_admin(msg)
        sys.exit(1)

# =============================================================================
# EXECUÇÃO DO SCRIPT
# =============================================================================

if __name__ == "__main__":
    main()
