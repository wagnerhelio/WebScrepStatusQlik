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
    os.system('chcp 65001 > nul')

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

# Carrega variáveis do ambiente do arquivo .env
load_dotenv()

# Configurações da Evolution API
evo_base_url = os.getenv("EVOLUTION_BASE_URL", "http://localhost:8080")
evo_api_token = os.getenv("EVOLUTION_API_TOKEN")
evo_instance_id = os.getenv("EVOLUTION_INSTANCE_NAME")
evo_instance_token = os.getenv("EVOLUTION_INSTANCE_ID")
evo_grupo = os.getenv("EVO_DESTINO_GRUPO")
evo_destino = os.getenv("EVO_DESTINO")

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
    
    # Lista todos os arquivos .py na pasta pysql/
    scripts_python = [
        f for f in os.listdir(pysql_dir) 
        if f.endswith('.py') and f != '__init__.py'
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
                    env=env
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
            print(f"⏰ Timeout ao executar {descricao}")
            resultados[script] = f"Timeout ao executar {descricao}"
        except Exception as e:
            print(f"❌ Erro ao executar {descricao}: {e}")
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

def gerar_resumo_tempos(dados, nome_script):
    """
    Gera um resumo formatado dos tempos de execução.
    
    Args:
        dados (dict): Dados JSON dos tempos de execução
        nome_script (str): Nome do script analisado
        
    Returns:
        str: Resumo formatado dos tempos
    """
    try:
        if not dados:
            return f"Nenhum dado de tempo disponível para {nome_script}"
        
        # Pega a execução mais recente
        timestamps = sorted(dados.keys(), reverse=True)
        if not timestamps:
            return f"Nenhum timestamp disponível para {nome_script}"
        
        execucao_recente = dados[timestamps[0]]
        
        # Calcula estatísticas
        tempos = list(execucao_recente.values())
        tempo_total = sum(tempos)
        tempo_medio = tempo_total / len(tempos) if tempos else 0
        tempo_max = max(tempos) if tempos else 0
        tempo_min = min(tempos) if tempos else 0
        
        # Formata o resumo
        resumo = f"📊 **{nome_script.upper()}**\n"
        resumo += f"Última execução: {timestamps[0][:19].replace('T', ' ')}\n"
        resumo += f"Tempo total: {tempo_total:.2f}s\n"
        resumo += f"Tempo médio: {tempo_medio:.2f}s\n"
        resumo += f"Tempo máximo: {tempo_max:.2f}s\n"
        resumo += f"Tempo mínimo: {tempo_min:.2f}s\n"
        
        # Detalhes por consulta
        resumo += "\n**Tempos por consulta:**\n"
        for consulta, tempo in execucao_recente.items():
            resumo += f"• {consulta}: {tempo:.2f}s\n"
        
        return resumo
        
    except Exception as e:
        return f"Erro ao gerar resumo para {nome_script}: {str(e)}"

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
    if ext == ".pdf":
        mimetype = "application/pdf"
    elif ext == ".json":
        mimetype = "application/json"
    elif ext == ".txt":
        mimetype = "text/plain"
    else:
        mimetype = "application/octet-stream"
    
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
# ENVIO DE RESUMOS DE TEMPOS
# =============================================================================

def enviar_resumos_tempo():
    """Envia resumos de tempos de execução para todos os destinos."""
    print("📊 Enviando resumos de tempos de execução...")
    
    # Analisa os tempos de execução
    resumos = analisar_tempos_execucao()
    
    if not resumos:
        mensagem = "Nenhum resumo de tempo de execução disponível no momento."
        enviar_para_todos_destinos(enviar_mensagem_texto, mensagem)
        return
    
    # Monta o resumo concatenado
    resumo_concat = "⏱️ **RESUMOS DE TEMPOS DE EXECUÇÃO PYSQL**\n\n"
    
    for nome_script, resumo in resumos.items():
        resumo_concat += f"{resumo}\n\n"
        resumo_concat += "─" * 50 + "\n\n"
    
    # Envia para todos os destinos
    enviar_para_todos_destinos(enviar_mensagem_texto, resumo_concat)

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
    for arquivo in arquivos_pdf:
        caminho_completo = os.path.join(reports_pysql_dir, arquivo)
        print(f"📤 Enviando: {arquivo}")
        enviar_para_todos_destinos(enviar_arquivo_para, caminho_completo)



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
        for arquivo in arquivos_erro:
            enviar_para_todos_destinos(enviar_arquivo_para, arquivo)
    else:
        # Envia mensagem de que não há erros
        mensagem = "✅ Nenhum erro encontrado nas consultas PySQL."
        enviar_para_todos_destinos(enviar_mensagem_texto, mensagem)

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
            enviar_resumos_tempo()
        except KeyboardInterrupt:
            print("⚠️ Envio interrompido - continuando...")
        
        print("\n" + "="*60)
        print("📄 ENVIO DE RELATÓRIOS PDF")
        print("="*60)
        try:
            enviar_relatorios_pdf()
        except KeyboardInterrupt:
            print("⚠️ Envio interrompido - continuando...")
        

        
        print("\n" + "="*60)
        print("📋 ENVIO DE LOGS DE ERRO")
        print("="*60)
        try:
            enviar_logs_erro()
        except KeyboardInterrupt:
            print("⚠️ Envio interrompido - continuando...")
        
        print("\n" + "="*60)
        print("🧹 LIMPEZA DAS PASTAS")
        print("="*60)
        try:
            limpar_pastas_apos_envio()
        except KeyboardInterrupt:
            print("⚠️ Limpeza interrompida - continuando...")
        
        print("\n✅ Processo PySQL finalizado com sucesso!")
        
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
