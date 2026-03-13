import os
import oracledb as cx_Oracle
import time
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
import numpy as np  
import seaborn as sns
from fpdf import FPDF
from dotenv import load_dotenv
from tqdm import tqdm
from datetime import datetime, timedelta
import json
import sys
import threading

# Lock para serializar saída da barra de progresso (evita duas consultas misturarem na mesma linha)
_progress_lock = threading.Lock()

# Define o diretório base do script
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)  # Volta um nível para a raiz do projeto
os.chdir(SCRIPT_DIR)

# Configuração de encoding para evitar problemas no Windows
if sys.platform.startswith('win'):
    try:
        # Configura o console para UTF-8
        os.system('chcp 65001 > nul')
        
        # Força UTF-8 para stdout e stderr
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8')
        if hasattr(sys.stderr, 'reconfigure'):
            sys.stderr.reconfigure(encoding='utf-8')
        else:
            # Fallback para versões mais antigas do Python
            import codecs
            sys.stdout = codecs.getwriter('utf-8')(sys.stdout.detach())
            sys.stderr = codecs.getwriter('utf-8')(sys.stderr.detach())
    except:
        # Se falhar, mantém o stdout original
        pass

load_dotenv(os.path.join(PROJECT_ROOT, '.env'))
matplotlib.use('Agg')  # Configura o backend antes de importar pyplot

def safe_str(item):
    return str(item) if item is not None else ''

def safe_print_progress(text):
    """Função segura para imprimir progresso no Windows"""
    try:
        # Tenta imprimir com UTF-8
        sys.stdout.write(text)
        sys.stdout.flush()
    except UnicodeEncodeError:
        # Fallback para ASCII se UTF-8 falhar
        try:
            safe_text = text.encode('ascii', 'replace').decode('ascii')
            sys.stdout.write(safe_text)
            sys.stdout.flush()
        except:
            # Último fallback - apenas mostra uma mensagem simples
            sys.stdout.write('\rProgresso...')
            sys.stdout.flush()
    except Exception as e:
        # Fallback genérico para qualquer erro
        try:
            # Remove caracteres problemáticos
            safe_text = text.replace('█', '#').replace('░', '-').replace('í', 'i').replace('ó', 'o')
            sys.stdout.write(safe_text)
            sys.stdout.flush()
        except:
            sys.stdout.write('\rProgresso...')
            sys.stdout.flush()

def salvar_tempos_execucao(tempos_execucao, arquivo=None):
    """Salva os tempos de execução em um arquivo JSON"""
    if arquivo is None:
        arquivo = os.path.join(PROJECT_ROOT, 'pysql', 'reports_pysql', 'feminicidios_tempos_execucao.json')
    try:
        # Cria o diretório se não existir
        os.makedirs(os.path.dirname(arquivo), exist_ok=True)
        
        # Carrega tempos existentes se o arquivo existir
        tempos_historicos = {}
        if os.path.exists(arquivo):
            try:
                with open(arquivo, 'r', encoding='utf-8') as f:
                    tempos_historicos = json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                tempos_historicos = {}
        
        # Adiciona a nova execução com timestamp
        timestamp = datetime.now().isoformat()
        tempos_historicos[timestamp] = tempos_execucao
        
        # Mantém apenas as últimas 10 execuções para calcular a média
        if len(tempos_historicos) > 10:
            # Remove as execuções mais antigas
            timestamps_ordenados = sorted(tempos_historicos.keys())
            for ts in timestamps_ordenados[:-10]:
                del tempos_historicos[ts]
        
        # Salva o arquivo atualizado
        with open(arquivo, 'w', encoding='utf-8') as f:
            json.dump(tempos_historicos, f, indent=2, ensure_ascii=False)
            
        print(f"Tempos de execução salvos em: {arquivo}")
        
    except Exception as e:
        print(f"Erro ao salvar tempos de execução: {e}")

def carregar_tempos_execucao(arquivo=None):
    """Carrega os tempos de execução históricos e calcula a média"""
    if arquivo is None:
        arquivo = os.path.join(PROJECT_ROOT, 'pysql', 'reports_pysql', 'feminicidios_tempos_execucao.json')
    try:
        if not os.path.exists(arquivo):
            return {}
        
        with open(arquivo, 'r', encoding='utf-8') as f:
            tempos_historicos = json.load(f)
        
        if not tempos_historicos:
            return {}
        
        # Calcula a média dos tempos para cada consulta
        tempos_medios = {}
        consultas = list(next(iter(tempos_historicos.values())).keys())
        
        for consulta in consultas:
            tempos_consulta = []
            for execucao in tempos_historicos.values():
                if consulta in execucao:
                    tempos_consulta.append(execucao[consulta])
            
            if tempos_consulta:
                tempos_medios[consulta] = sum(tempos_consulta) / len(tempos_consulta)
        
        return tempos_medios
        
    except Exception as e:
        print(f"Erro ao carregar tempos de execução: {e}")
        return {}

def mostrar_progresso_tempo(nome_consulta, tempo_inicio, tempo_medio_esperado):
    """Mostra uma barra de progresso baseada no tempo médio esperado"""
    if tempo_medio_esperado <= 0:
        return
    
    tempo_atual = time.time() - tempo_inicio
    progresso = min(tempo_atual / tempo_medio_esperado, 1.0)
    
    # Cria uma barra de progresso simples
    largura_barra = 50
    posicao = int(progresso * largura_barra)
    barra = '█' * posicao + '░' * (largura_barra - posicao)
    percentual = progresso * 100
    
    # Limpa a linha atual e mostra o progresso
    progress_text = f'\r{nome_consulta}: [{barra}] {percentual:.1f}% ({tempo_atual:.1f}s/{tempo_medio_esperado:.1f}s)'
    safe_print_progress(progress_text)
    
    if progresso >= 1.0:
        print()  # Nova linha quando terminar

def executar_com_progresso(nome, query, cursor, tempos_medios):
    """Executa uma query com barra de progresso baseada no tempo médio esperado.
    Em TTY a barra atualiza no lugar com \\r; em pipe cada atualização vai com \\n para o orquestrador reescrever na mesma linha."""
    start = time.time()
    tempo_medio_esperado = tempos_medios.get(nome, 0)
    progresso_thread = None
    is_tty = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()

    if tempo_medio_esperado > 0:
        import time as time_module
        def mostrar_progresso():
            while True:
                tempo_atual = time.time() - start
                progresso = min(tempo_atual / tempo_medio_esperado, 1.0)
                largura_barra = 50
                posicao = int(progresso * largura_barra)
                barra = '#' * posicao + '-' * (largura_barra - posicao)
                percentual = progresso * 100
                progress_text = f'\r       [{barra}] {percentual:.1f}% ({tempo_atual:.1f}s/{tempo_medio_esperado:.1f}s)'
                with _progress_lock:
                    if is_tty:
                        safe_print_progress(progress_text)
                    else:
                        print(progress_text.strip().lstrip("\r"), flush=True)
                if progresso >= 1.0:
                    break
                time_module.sleep(0.1)
        progresso_thread = threading.Thread(target=mostrar_progresso)
        progresso_thread.daemon = True
        progresso_thread.start()

    # Executa a query
    cursor.execute(query)
    
    # Processa o resultado
    if nome in ["Feminicídios Comparativo por Município", "Feminicídios Comparativo por 2 Anos","Feminicídios Comparativo por Todos os Anos","Feminicídios Comparativo por Regiões","Feminicídios Comparativo por Regiões dia atual","Feminicídios Comparativo por Dia","Feminicídios Comparativo por Dia por Regiões","Feminicídios Comparativo por Mes por Regiões","Feminicídios Comparativo por Semana por Regiões","Feminicídios em Presídios","Feminicídios Comparativo por Município Top 20","Feminicídios Comparativo por Risp","Feminicídios Comparativo por Aisp"]:
        columns = [str(col[0]) for col in cursor.description]
        rows = [list(row) for row in cursor.fetchall()]
        resultado = (columns, rows)
    else:
        resultado = cursor.fetchone()
    
    end = time.time()
    tempo_execucao = end - start
    
    if progresso_thread is not None:
        progresso_thread.join(timeout=0.5)
        with _progress_lock:
            print()  # Nova linha ao concluir a barra

    return resultado, tempo_execucao

# Cria a pasta pysql/img_reports se não existir
relatorio_dir = os.path.join(PROJECT_ROOT, 'pysql', 'img_reports')
if not os.path.exists(relatorio_dir):
    os.makedirs(relatorio_dir)

# Verifica se o diretório foi criado e tem permissões de escrita
if not os.path.exists(relatorio_dir):
    raise RuntimeError(f"Não foi possível criar o diretório {relatorio_dir}")

# Testa se é possível escrever no diretório
try:
    test_file = os.path.join(relatorio_dir, 'test.txt')
    with open(test_file, 'w') as f:
        f.write('test')
    os.remove(test_file)
except Exception as e:
    raise RuntimeError(f"Não é possível escrever no diretório {relatorio_dir}: {e}")

# Define o diretório onde está o logo
logo_dir = os.path.join(PROJECT_ROOT, 'pysql', 'img_reports')

class PDFComRodape(FPDF):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tempo_homicidio = ""
        self.tempo_feminicidio = ""
        self.tempo_municipio = ""
        self.tempo_homicidio_comparativo_dois_anos = ""
        self.tempo_homicidio_comparativo_todos_anos = ""
        
        # Configura margens para otimizar espaço
        self.set_margins(10, 2, 10)

    def footer(self):
        self.set_y(-10)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(80, 80, 80)
        if self.tempo_homicidio and self.tempo_feminicidio:
            self.cell(0, 4, f'Tempo de execução da consulta Homicídio: {self.tempo_homicidio} segundos', ln=1, align='C')
            self.cell(0, 4, f'Tempo de execução da consulta Feminicídio: {self.tempo_feminicidio} segundos', ln=1, align='C')
        if self.tempo_municipio:
            self.cell(0, 4, f'Tempo de execução da consulta por município: {self.tempo_municipio} segundos', ln=1, align='C')
        if self.tempo_homicidio_comparativo_dois_anos:
            self.cell(0, 4, f'Tempo de execução da consulta tempo_homicidio_comparativo_dois_anos: {self.tempo_homicidio_comparativo_dois_anos} segundos', ln=1, align='C')
        if self.tempo_homicidio_comparativo_todos_anos:
            self.cell(0, 4, f'Tempo de execução da consulta tempo_homicidio_comparativo_todos_anos: {self.tempo_homicidio_comparativo_todos_anos} segundos', ln=1, align='C') 

# --- CONEXÃO ORACLE ---
# Ajuste dos tipos para o dsn
oracle_host = os.getenv('ORACLE_HOST')
oracle_port_str = os.getenv('ORACLE_PORT', '1521')
oracle_tns = os.getenv('ORACLE_TNS')

if not oracle_host or not oracle_port_str or not oracle_tns:
    raise ValueError('Variáveis de ambiente ORACLE_HOST, ORACLE_PORT e ORACLE_TNS devem estar definidas.')

oracle_port = int(oracle_port_str)
dsn = cx_Oracle.makedsn(
    oracle_host,
    oracle_port,
    service_name=oracle_tns
)

conn = cx_Oracle.connect(
    user=os.getenv('ORACLE_USER'),
    password=os.getenv('ORACLE_PASSWORD'),
    dsn=dsn
)

cursor = conn.cursor()
print("Conectado ao Oracle. Carregando SQLs do GitLab...", flush=True)
# Metadados das queries: (nome de exibição, nome do arquivo .sql) - SQLs no GitLab
QUERY_METADATA_FEMINICIDIOS = [
    ("Feminicídios", "feminicidios.sql"),
    ("Feminicídios Comparativo por Município", "feminicidios_comparativo_municipios.sql"),
    ("Feminicídios Comparativo por 2 Anos", "feminicidios_comparativo_dois_anos.sql"),
    ("Feminicídios Comparativo por Todos os Anos", "feminicidios_comparativo_todos_anos.sql"),
    ("Feminicídios Comparativo por Dia", "feminicidios_comparativo_dia.sql"),
    ("Feminicídios Comparativo por Regiões dia atual", "feminicidios_comparativo_regioes_dia_atual.sql"),
    ("Feminicídios Comparativo por Regiões", "feminicidios_comparativo_regioes.sql"),
    ("Feminicídios Comparativo por Dia por Regiões", "feminicidios_comparativo_regioes_dia.sql"),
    ("Feminicídios Comparativo por Mes por Regiões", "feminicidios_comparativo_regioes_mes.sql"),
    ("Feminicídios Comparativo por Semana por Regiões", "feminicidios_comparativo_regioes_semana.sql"),
    ("Feminicídios em Presídios", "feminicidios_em_presidios.sql"),
    ("Feminicídios Comparativo por Município Top 20", "feminicidios_comparativo_municipios_top_20.sql"),
    ("Feminicídios Comparativo por Risp", "feminicidios_comparativo_risp.sql"),
    ("Feminicídios Comparativo por Aisp", "feminicidios_comparativo_aisp.sql"),
]

# Carrega SQLs do GitLab (extract_odisseu_oracle/relatorio_feminicidios no repositório etl-oracle)
from sql_loader_gitlab import fetch_sql_from_gitlab

_gitlab_base = os.getenv("GITLAB_BASE_URL")
_gitlab_project = os.getenv("GITLAB_PROJECT")
_gitlab_token = os.getenv("GITLAB_TOKEN")
_gitlab_branch = os.getenv("GITLAB_BRANCH", "main")
_sql_path = os.getenv("GITLAB_SQL_PATH_FEMINICIDIOS", "extract_odisseu_oracle/relatorio_feminicidios")
queries = []
total_sqls = len(QUERY_METADATA_FEMINICIDIOS)
for idx, (display_name, sql_filename) in enumerate(QUERY_METADATA_FEMINICIDIOS, 1):
    print(f"  [{idx}/{total_sqls}] Carregando {sql_filename}...", flush=True)
    file_path = _sql_path.rstrip("/") + "/" + sql_filename
    sql_text = fetch_sql_from_gitlab(file_path, _gitlab_base, _gitlab_project, _gitlab_token, _gitlab_branch)
    if not sql_text:
        raise RuntimeError(f"SQL vazia para {display_name} ({sql_filename})")
    queries.append((display_name, sql_text))
print(f"  OK: {len(queries)} SQLs carregadas.\n", flush=True)
if not queries:
    raise RuntimeError("Nenhuma query carregada do GitLab. Verifique GITLAB_* no .env.")


# Carrega tempos médios de execução históricos
tempos_medios = carregar_tempos_execucao()

resultados = {}
tempos_execucao = {}
total_queries = len(queries)
print(f"Executando {total_queries} consultas no Oracle:\n", flush=True)

for idx, (nome, query) in enumerate(queries, 1):
    print(f"  [{idx}/{total_queries}] {nome}...", flush=True)
    # Executa a query com barra de progresso
    resultado, tempo_execucao = executar_com_progresso(nome, query, cursor, tempos_medios)
    resultados[nome] = resultado
    tempos_execucao[nome] = tempo_execucao
    tempo_medio_esperado = tempos_medios.get(nome, 0)
    if tempo_medio_esperado > 0:
        print(f"       Concluído em {tempo_execucao:.2f}s (esperado: {tempo_medio_esperado:.2f}s)", flush=True)
    else:
        print(f"       Concluído em {tempo_execucao:.2f}s", flush=True)

print("\nConsultas concluídas. Gerando PDF e gráficos...", flush=True)

# Extrai os resultados
feminicidios_hoje, feminicidios_ontem, feminicidios_mes, feminicidios_mes_ontem, feminicidios_ano, feminicidios_ano_ontem = resultados["Feminicídios"]

hoje = datetime.now()
dia_atual = hoje.day
mes_atual = hoje.strftime('%b').capitalize()  # Ex: 'Jul'
ano_atual = hoje.year
ontem = hoje - timedelta(days=1)
ontem_data = (hoje - timedelta(days=1)).strftime('%d/%m/%Y')
mes_ontem = ontem.strftime('%b').capitalize()  # Ex: 'Jul'
dia_ontem = ontem.day
ano_anterior = ano_atual - 1

# Textos de rodapé de período (utilizado na consulta): do dia 01/01/YYYY até DD/MM/YYYY HH:MM:SS
texto_periodo_ate_hoje = f"De 01/01/{ano_atual} até {hoje.strftime('%d/%m/%Y %H:%M:%S')}"
texto_periodo_ate_ontem = f"De 01/01/{ano_atual} até {ontem_data}"
texto_periodo_anterior = f"De 01/01/{ano_anterior} até {ontem_data}"

# --- INÍCIO DA GERAÇÃO DO PDF ---
pdf = PDFComRodape()
pdf.add_page()

# --- CABEÇALHO DO PDF (LOGO E TÍTULO INSTITUCIONAL) ---
logo_path = os.path.join(logo_dir, 'LogoRelatorio.jpg')
if os.path.exists(logo_path):
    pdf.image(logo_path, x=10, y=1, w=190)
else:
    print(f"Logo não encontrado: {logo_path}")
pdf.ln(25)

# --- CONTEXTO: CAIXA DE TEXTO COM INDICADORES ---
# Gera a caixa com os principais indicadores de homicídios e feminicídios
caixa_x = 10
caixa_y = pdf.get_y() + 5
caixa_w = 110
caixa_h = 45  # altura estimada, pode ser ajustada

pdf.set_xy(caixa_x, caixa_y)
pdf.set_draw_color(0, 100, 0)  # verde escuro
pdf.set_line_width(0.5)
pdf.rect(caixa_x, caixa_y, caixa_w, caixa_h)

# --- Monta o texto dos quantitativos, todos dentro da caixa ---
linha_y = caixa_y + 3
linha_h = 7
margem = 4

def escreve_linha_valor(texto, valor):
    pdf.set_xy(caixa_x + margem, linha_y)
    pdf.set_font('Arial', '', 10)
    largura_texto = pdf.get_string_width(texto + ': ')
    pdf.cell(largura_texto, linha_h, texto + ': ', ln=0)
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(pdf.get_string_width(str(valor)), linha_h, str(valor), ln=1)

# Indicadores principais
escreve_linha_valor(f'Feminicídios em {ontem.strftime("%d/%m/%Y")}', feminicidios_ontem)
linha_y += linha_h
escreve_linha_valor(f'Feminicídios no mês {mes_ontem}', feminicidios_mes_ontem)
linha_y += linha_h
escreve_linha_valor(f'Feminicídios no ano {ano_atual}', feminicidios_ano)
linha_y += linha_h

# Observação
pdf.set_xy(caixa_x + margem, linha_y)
pdf.set_font('Arial', 'I', 8)
pdf.cell(0, linha_h, 'Obs.: No número de Feminicídios estão contabilizados os Homicídios.', ln=1)

# --- KPIs À DIREITA ---
# Exibe os KPIs de homicídios do dia e do mês à direita da caixa de indicadores

kpi_x = caixa_x + caixa_w + 10
kpi_y = caixa_y  # alinhado com a caixa
pdf.set_xy(kpi_x, kpi_y)

#titulo kpi feminicidios em dia
pdf.set_font('Arial', '', 12)
pdf.set_text_color(100, 100, 100) 
pdf.cell(0, 8, f'Feminicídios em: {hoje.strftime("%d/%m/%Y")}', ln=1)

#valor kpi feminicidios em dia
pdf.set_font('Arial', 'B', 28)
pdf.set_text_color(30, 80, 160)
pdf.set_x(kpi_x)
pdf.cell(0, 15, str(feminicidios_hoje), ln=1, align='C')

#rodape kpi feminicidios em dia
pdf.set_font('Arial', 'I', 8)
pdf.set_text_color(0, 0, 0)
pdf.set_x(kpi_x)
pdf.cell(0, 8, texto_periodo_ate_hoje, ln=1, align='L')

#titulo kpi feminicidios em mes
pdf.set_font('Arial', '', 12)
pdf.set_text_color(100, 100, 100)
pdf.set_x(kpi_x)
pdf.cell(0, 8, f'Feminicídios em mês: {mes_atual}', ln=1)

#valor kpi feminicidios em mes
pdf.set_font('Arial', 'B', 28)
pdf.set_text_color(30, 80, 160)
pdf.set_x(kpi_x)
pdf.cell(0, 15, str(feminicidios_mes), ln=1, align='C')

#rodape kpi feminicidios em mes
pdf.set_font('Arial', 'I', 8) 
pdf.set_text_color(0, 0, 0)
pdf.set_x(kpi_x)
pdf.cell(0, 8, texto_periodo_ate_hoje, ln=1, align='L')
 
 # Y final após os KPIs (usado para posicionar o próximo bloco abaixo do mais baixo)
kpi_end_y = pdf.get_y()

# ------------------------------------------------- TABELA DE REGIAO - COMPARATIVO MENSAL ATUAL E ACUMULADO -------------------------------------------------
# Posiciona abaixo do bloco mais baixo (caixa à esquerda ou KPIs à direita), com espaço para não grudar
y_after_header = max(caixa_y + caixa_h, kpi_end_y) + 8
pdf.set_xy(pdf.l_margin, y_after_header)

columns_regiao_observatorio_atualizada = [
    "REGIÃO",
    f"{mes_atual}/{ano_anterior} (fechado)",
    f"{mes_atual}/{ano_anterior} (até dia {dia_atual})",
    f"{mes_atual}/{ano_atual} (até dia {dia_atual})",
    "%",
    f"Acumulado Jan a {mes_atual} {ano_anterior} (até dia {dia_atual})",
    f"Acumulado Jan a {mes_atual} {ano_atual} (até dia {dia_atual})",
    "%",
    "Índice por 100K hab."
]

columns_regiao_observatorio, rows_regiao_observatorio = resultados["Feminicídios Comparativo por Regiões dia atual"]


# Título da tabela
pdf.set_font('Arial', 'B', 12)
pdf.set_text_color(0, 0, 0)  # Preto
titulo_regiao_observatorio = f'Feminicídios por regiões - comparativo dia atual e acumulado :'
pdf.cell(0, 10, titulo_regiao_observatorio, ln=1, align='L')

col_widths_regiao_observatorio = [25, 20, 20, 20, 15, 23, 23, 15, 23]  # 9 colunas
# Cabeçalho da tabela de regiões observatório (ajustado para quebra de linha, altura uniforme)
pdf.set_font('Arial', 'B', 7)
pdf.set_fill_color(230, 230, 230)
pdf.set_draw_color(0, 0, 0)  # Preto para borda
pdf.set_text_color(0, 0, 0)  # Preto para texto

x_inicio = pdf.get_x()
y_inicio = pdf.get_y()
altura_linha = 6

# Calcula a altura máxima necessária para cada célula do cabeçalho
alturas = []
linhas_texto = []
for i, col in enumerate(columns_regiao_observatorio_atualizada):
    largura = col_widths_regiao_observatorio[i]
    # Divide o texto em linhas para a largura da célula
    linhas = pdf.multi_cell(largura, altura_linha, str(col).upper(), 0, 'C', split_only=True)
    linhas_texto.append(linhas)
    alturas.append(len(linhas) * altura_linha)
altura_max = max(alturas)

# Desenha cada célula do cabeçalho com altura máxima e texto centralizado
x = x_inicio
for i, col in enumerate(columns_regiao_observatorio_atualizada):
    largura = col_widths_regiao_observatorio[i]
    linhas = linhas_texto[i]
    n_linhas = len(linhas)
    y = y_inicio
    # Centraliza verticalmente o texto
    y_texto = y + (altura_max - n_linhas * altura_linha) / 2
    pdf.rect(x, y, largura, altura_max, 'DF')
    pdf.set_xy(x, y_texto)
    for linha in linhas:
        pdf.cell(largura, altura_linha, linha, 0, 2, 'C')
    x += largura
pdf.set_xy(x_inicio, y_inicio + altura_max)

# Dados da tabela de regiões observatório
pdf.set_font('Arial', '', 7)
pdf.set_text_color(0, 0, 0)  # Preto para texto
for row in rows_regiao_observatorio:
    for i, item in enumerate(row):
        # Coloração e formatação para as colunas de %
        if i in [4, 7]:  # Índices das colunas de %
            valor = float(item) if item is not None else 0
            texto = f"{valor:.2f}%"
            if valor > 0:
                pdf.set_fill_color(220, 20, 60)  # vermelho no background
                pdf.set_text_color(255, 255, 255)  # texto branco
            elif valor < 0:
                pdf.set_fill_color(0, 128, 0)    # verde no background
                pdf.set_text_color(255, 255, 255)  # texto branco
            else:
                pdf.set_fill_color(255, 255, 255)  # fundo branco
                pdf.set_text_color(0, 0, 0)      # texto preto
            pdf.cell(col_widths_regiao_observatorio[i], 6, texto, 1, 0, 'C', fill=True)
            pdf.set_fill_color(255, 255, 255)  # reset do background
            pdf.set_text_color(0, 0, 0)  # reset do texto
        else:
            pdf.cell(col_widths_regiao_observatorio[i], 6, safe_str(item), 1, 0, 'C')
    pdf.ln()

# Calcula e adiciona linha de TOTAL
if rows_regiao_observatorio:
    # Inicializa totais
    totais = [0] * len(rows_regiao_observatorio[0])
    
    # Calcula totais para colunas numéricas (excluindo a primeira coluna que é texto)
    for row in rows_regiao_observatorio:
        for i, item in enumerate(row):
            if i > 0:  # Pula a primeira coluna (REGIÃO)
                try:
                    if i in [4, 7]:  # Colunas de porcentagem
                        totais[i] += float(item) if item is not None else 0
                    else:  # Colunas numéricas
                        totais[i] += int(item) if item is not None else 0
                except (ValueError, TypeError):
                    pass  # Ignora valores não numéricos
    
    # Cria linha de total
    linha_total = ["GOIÁS"]
    for i in range(1, len(totais)):
        if i in [4, 7]:  # Colunas de porcentagem
            linha_total.append(f"{totais[i]:.2f}")
        else:  # Colunas numéricas
            linha_total.append(str(totais[i]))
    
    # Adiciona linha de total com formatação especial
    pdf.set_font('Arial', 'B', 7)  # Negrito para destacar
    for i, item in enumerate(linha_total):
        # Coloração e formatação para as colunas de %
        if i in [4, 7]:  # Índices das colunas de %
            valor = float(item) if item is not None else 0
            texto = f"{valor:.2f}%"
            if valor > 0:
                pdf.set_fill_color(220, 20, 60)  # vermelho no background
                pdf.set_text_color(255, 255, 255)  # texto branco
            elif valor < 0:
                pdf.set_fill_color(0, 128, 0)    # verde no background
                pdf.set_text_color(255, 255, 255)  # texto branco
            else:
                pdf.set_fill_color(255, 255, 255)  # fundo branco
                pdf.set_text_color(0, 0, 0)      # texto preto
            pdf.cell(col_widths_regiao_observatorio[i], 6, texto, 1, 0, 'C', fill=True)
            pdf.set_fill_color(255, 255, 255)  # reset do background
            pdf.set_text_color(0, 0, 0)  # reset do texto
        else:
            pdf.cell(col_widths_regiao_observatorio[i], 6, safe_str(item), 1, 0, 'C')
    pdf.ln()
    pdf.set_font('Arial', '', 7)  # Volta para fonte normal

pdf.set_font('Arial', 'I', 9)
pdf.cell(0, 8, texto_periodo_ate_hoje, ln=1, align='L')

# ------------------------------------------------- TABELA DE HOMICÍDIOS POR MUNICÍPIO DIÁRIO-------------------------------------------------
# Gera a tabela de homicídios por município

columns_homicidio_municipio, rows_homicidio_municipio = resultados["Feminicídios Comparativo por Município"]  

# Espaço antes da tabela
pdf.ln(1)

# Título da tabela
pdf.set_font('Arial', 'B', 12)
pdf.set_text_color(0, 0, 0)  # Preto
titulo_municipio = f'Feminicídios - até dia atual por município :'
pdf.cell(0, 10, titulo_municipio, ln=1, align='L')

# Cabeçalho da tabela de município (exibir NI em vez de NF para alinhar com a legenda)
col_widths_municipio = [45, 20, 20, 20, 35, 12, 12, 12, 12]  # 9 colunas: municipio_nome, id_rai, datafato, horafato, dataultimaatualizacao, total, F, M, NI
pdf.set_font('Arial', 'B', 7)
pdf.set_fill_color(230, 230, 230)
pdf.set_draw_color(0, 0, 0)  # Preto para borda
pdf.set_text_color(0, 0, 0)  # Preto para texto
for i, col in enumerate(columns_homicidio_municipio):
    cab = str(col).upper().replace('NF', 'NI')
    pdf.cell(col_widths_municipio[i], 6, cab, 1, 0, 'C', fill=True)
pdf.ln()

# Dados da tabela de município (TOTAL = F + M + NF, corrigido na exibição)
pdf.set_font('Arial', '', 7)
pdf.set_text_color(0, 0, 0)  # Preto para texto

for row in rows_homicidio_municipio:
    for i, item in enumerate(row):
        if i == 5 and len(row) >= 9:  # Coluna TOTAL: usar soma F+M+NF
            try:
                f_val = int(row[6]) if row[6] is not None else 0
                m_val = int(row[7]) if row[7] is not None else 0
                nf_val = int(row[8]) if row[8] is not None else 0
                item = str(f_val + m_val + nf_val)
            except (ValueError, TypeError):
                pass
        pdf.cell(col_widths_municipio[i], 6, safe_str(item), 1, 0, 'C')
    pdf.ln()

pdf.set_font('Arial', 'I', 6)
pdf.set_text_color(120, 120, 120)
pdf.cell(0, 4, 'F - FEMININO | M - MASCULINO | NI - NÃO INFORMADO', ln=1, align='L')
pdf.set_text_color(0, 0, 0)
pdf.set_font('Arial', 'I', 9)
pdf.cell(0, 8, texto_periodo_ate_hoje, ln=1, align='L')
# ------------------------------------------------- GRAFICO DE HOMICÍDIOS ÚLTIMOS 2 ANOS -------------------------------------------------
# Gera o gráfico de linhas comparando homicídios mês a mês dos dois últimos anos
colunas_homicidio_2anos, linhas_homicidio_2anos = resultados["Feminicídios Comparativo por 2 Anos"]

# Título do grafico
pdf.set_font('Arial', 'B', 12)
pdf.set_text_color(0, 0, 0)
titulo_homicidio_2anos = f'Feminicídios - Comparativo ano atual com o último ano :'
pdf.cell(0, 10, titulo_homicidio_2anos, ln=1, align='L')

# Cria o DataFrame
df_homicidio_2anos = pd.DataFrame(linhas_homicidio_2anos, columns=colunas_homicidio_2anos)

# Obtém as colunas de meses diretamente do DataFrame (excluindo ANO_FATO)
colunas_meses = [col for col in df_homicidio_2anos.columns if col != 'ANO_FATO']

plt.figure(figsize=(10, 2.0))
for _, linha in df_homicidio_2anos.iterrows():
    ano = int(linha['ANO_FATO'])
    
    # Para o ano atual, usa apenas os meses até o mês de ontem
    if ano == datetime.now().year:
        # Obtém o mês de ontem como número (1-12)
        mes_ontem_num = (hoje - timedelta(days=1)).month
        # Seleciona apenas os meses até o mês de ontem
        meses_plot = colunas_meses[:mes_ontem_num]
    else:
        # Para anos anteriores, usa todos os meses
        meses_plot = colunas_meses
    
    # Extrai os valores diretamente da linha do DataFrame
    valores = [int(linha[m]) if linha[m] is not None else 0 for m in meses_plot]
    
    sns.lineplot(x=meses_plot, y=valores, marker='o', label=ano)
    for i, v in enumerate(valores):
        if v > 0:
            plt.text(i, v, str(v), ha='center', va='bottom', fontsize=8, bbox=dict(facecolor='white', alpha=0.8, edgecolor='none'))

plt.legend(title='ANO', bbox_to_anchor=(1.00, 1), loc='upper left', fontsize=8, title_fontsize=9)
plt.ylabel('Homicídios')
plt.yticks([])
plt.xlabel('')

# Salva o gráfico com tratamento de erro
try:
    plt.savefig(os.path.join(relatorio_dir, 'grafico_feminicidio_2anos.png'), dpi=150, bbox_inches='tight')
except Exception as e:
    print(f"Erro ao salvar gráfico: {e}")
    # Tenta salvar com configurações mais básicas
    try:
        plt.savefig(os.path.join(relatorio_dir, 'grafico_feminicidio_2anos.png'), format='png', dpi=100)
    except Exception as e2:
        print(f"Erro ao salvar com configurações básicas: {e2}")
        # Cria um gráfico simples como fallback
        plt.figure(figsize=(10, 2.0))
        plt.text(0.5, 0.5, 'Gráfico não disponível', ha='center', va='center', transform=plt.gca().transAxes)
        plt.savefig(os.path.join(relatorio_dir, 'grafico_feminicidio_2anos.png'), format='png', dpi=100)
plt.close()

# Adiciona o DataFrame ao PDF
# Verifica se o arquivo existe antes de adicionar ao PDF
grafico_2anos_path = os.path.join(relatorio_dir, 'grafico_feminicidio_2anos.png')
if os.path.exists(grafico_2anos_path):
    pdf.image(grafico_2anos_path, x=5, w=200)
else:
    pdf.set_font('Arial', 'I', 10)
    pdf.cell(0, 8, 'Gráfico não disponível', ln=1, align='C')
pdf.set_font('Arial', 'I', 9)
pdf.cell(0, 6, texto_periodo_ate_ontem, ln=1, align='L')

# Adiciona uma nova página
pdf.add_page()
# ------------------------------------------------- TABELA DE HOMICÍDIOS POR MESES/ANOS  -------------------------------------------------
# Monta a tabela comparativa de homicídios por mês e ano
colunas_homicidio_todos_anos, linhas_homicidio_todos_anos = resultados["Feminicídios Comparativo por Todos os Anos"]
df_homicidio_todos_anos = pd.DataFrame(linhas_homicidio_todos_anos, columns=colunas_homicidio_todos_anos)

# Espaço antes da tabela (reduzido)
pdf.ln(0.5)

# Título da tabela
pdf.set_font('Arial', 'B', 12)
pdf.set_text_color(0, 0, 0)  # Preto
titulo_homicidio_todos_anos = f'Feminicídios comparativo por ano :'
pdf.cell(0, 10, titulo_homicidio_todos_anos, ln=1, align='L')

# Cabeçalho da tabela de meses/anos (com coluna TOTAL); larguras reduzidas e centralizadas na A4
col_widths_homicidio_todos_anos = [14] + [10]*12 + [12]  # ANO + 12 meses + TOTAL
largura_total_tabela = sum(col_widths_homicidio_todos_anos)
pagina_largura_util = 190
x_inicio_tabela = pdf.l_margin + (pagina_largura_util - largura_total_tabela) / 2
pdf.set_x(x_inicio_tabela)
pdf.set_font('Arial', 'B', 7)
pdf.set_fill_color(230, 230, 230)
pdf.set_draw_color(0, 0, 0)
pdf.set_text_color(0, 0, 0)
for i, col in enumerate(colunas_homicidio_todos_anos):
    pdf.cell(col_widths_homicidio_todos_anos[i], 6, str(col).upper(), 1, 0, 'C', fill=True)
pdf.cell(col_widths_homicidio_todos_anos[-1], 6, 'TOTAL', 1, 0, 'C', fill=True)
pdf.ln()

# Dados da tabela de meses/anos
pdf.set_font('Arial', '', 7)
pdf.set_text_color(0, 0, 0)  # Preto para texto
def safe_str_homicidio_todos_anos(item):
    return str(item) if item is not None else ''

# Adiciona zebragem (alternância de cores de fundo)
for idx, linha in enumerate(linhas_homicidio_todos_anos):
    pdf.set_x(x_inicio_tabela)
    if idx % 2 == 0:
        pdf.set_fill_color(255, 255, 255)
    else:
        pdf.set_fill_color(240, 240, 245)
    for i, item in enumerate(linha):
        pdf.cell(col_widths_homicidio_todos_anos[i], 6, safe_str_homicidio_todos_anos(item), 1, 0, 'C', fill=True)
    total_linha = sum(int(linha[i]) if linha[i] is not None else 0 for i in range(1, 13))
    pdf.cell(col_widths_homicidio_todos_anos[-1], 6, str(total_linha), 1, 0, 'C', fill=True)
    pdf.ln()

pdf.set_font('Arial', 'I', 9)
pdf.cell(0, 8, texto_periodo_ate_ontem, ln=1, align='L')

# ------------------------------------------------- GRAFICO COMPARATIVO POR DIA -------------------------------------------------
# Gera o gráfico comparativo de homicídios por dia
columns_dia, rows_dia = resultados["Feminicídios Comparativo por Dia"]

pdf.ln(3)

# Título do grafico
pdf.set_font('Arial', 'B', 12)
pdf.set_text_color(0, 0, 0)  # Preto
titulo_mes_atual = f'Feminicídios - Comparativo por dia no mês atual: {hoje.strftime("%b/%Y")}'
pdf.cell(0, 10, titulo_mes_atual, ln=1, align='L')

# Cria o DataFrame
df_dia = pd.DataFrame(rows_dia, columns=columns_dia)

# Ajusta tipos e nomes
if not df_dia.empty:
    df_dia['ANO'] = df_dia['ANO'].astype(int)
    df_dia['HOMICIDIOS'] = df_dia['HOMICIDIOS'].astype(int)

    # Pivot para barras agrupadas
    df_pivot = df_dia.pivot(index='DATA', columns='ANO', values='HOMICIDIOS').fillna(0)
    df_pivot = df_pivot.reindex(sorted(df_pivot.index, key=lambda x: int(x.split('/')[0])))

    plt.figure(figsize=(10, 2.0))
    anos = sorted(df_pivot.columns)
    bar_width = 0.4
    x = range(len(df_pivot.index))
    #cores = ['#3b3b98', '#218c5a']  # Azul e verde

    for i, ano in enumerate(anos):
        bars = plt.bar([xi + i*bar_width for xi in x], df_pivot[ano], width=bar_width, label=str(ano))
        #bars = plt.bar([xi + i*bar_width for xi in x], df_pivot[ano], width=bar_width, label=str(ano), color=cores[i % len(cores)])
        # Adiciona o valor acima de cada barra
        for bar in bars:
            height = bar.get_height()
            if height > 0:
                plt.text(
                    bar.get_x() + bar.get_width() / 2,
                    height + 0.1,
                    f'{int(height)}',
                    ha='center',
                    va='bottom',
                    fontsize=8
                )
    plt.legend(title='ANO', bbox_to_anchor=(1.00, 1), loc='upper left', fontsize=8, title_fontsize=9)
    plt.ylabel('Homicídios')
    plt.yticks([])
    plt.xticks([xi + bar_width/2 for xi in x], list(df_pivot.index), rotation=45)
    
    # Salva o gráfico com tratamento de erro
    try:
        plt.savefig(os.path.join(relatorio_dir, 'grafico_feminicidio_dia.png'), dpi=150, bbox_inches='tight')
    except Exception as e:
        print(f"Erro ao salvar gráfico: {e}")
        try:
            plt.savefig(os.path.join(relatorio_dir, 'grafico_feminicidio_dia.png'), format='png', dpi=100)
        except Exception as e2:
            print(f"Erro ao salvar com configurações básicas: {e2}")
            plt.figure(figsize=(10, 3.0))
            plt.text(0.5, 0.5, 'Gráfico não disponível', ha='center', va='center', transform=plt.gca().transAxes)
            plt.savefig(os.path.join(relatorio_dir, 'grafico_feminicidio_dia.png'), format='png', dpi=100)
    plt.close()

# Adiciona o DataFrame ao PDF 
# Verifica se o arquivo existe antes de adicionar ao PDF
grafico_dia_path = os.path.join(relatorio_dir, 'grafico_feminicidio_dia.png')
if os.path.exists(grafico_dia_path):
    pdf.image(grafico_dia_path, x=5, w=200)
else:
    pdf.set_font('Arial', 'I', 10)
    pdf.cell(0, 8, 'Gráfico não disponível', ln=1, align='C')
pdf.set_font('Arial', 'I', 9)
pdf.cell(0, 8, texto_periodo_ate_ontem, ln=1, align='L')

# ------------------------------------------------- TABELA COMPARATIVO POR DIA -------------------------------------------------


# Título da tabela
pdf.set_font('Arial', 'B', 12)
pdf.set_text_color(0, 0, 0)  # Preto
titulo_por_dia = f'Feminicídios comparativo por dia no mês atual :'
pdf.cell(0, 10, titulo_por_dia, ln=1, align='L')

# Transpõe para: colunas = dias, linhas = anos
df_tab = df_pivot.T

# Largura total disponível (ajuste conforme sua margem)
largura_total = 190
num_colunas = len(df_tab.columns)
col_width_ano = 12
col_width = (largura_total - col_width_ano) / num_colunas if num_colunas > 0 else largura_total

# Cabeçalho
dias = list(df_tab.columns)
pdf.set_font('Arial', 'B', 7)
pdf.set_fill_color(230, 230, 230)
pdf.set_draw_color(0, 0, 0)
pdf.set_text_color(0, 0, 0)
pdf.cell(col_width_ano, 6, 'Ano', 1, 0, 'C', fill=True)
for dia in dias:
    pdf.cell(col_width, 6, str(dia), 1, 0, 'C', fill=True)
pdf.ln()

# Linhas de dados (anos)
pdf.set_font('Arial', '', 7)
for ano, row in df_tab.iterrows():
    pdf.cell(col_width_ano, 6, str(ano), 1, 0, 'C')
    for valor in row:
        pdf.cell(col_width, 6, str(int(valor)), 1, 0, 'C')
    pdf.ln()

pdf.set_font('Arial', 'I', 9)
pdf.cell(0, 8, texto_periodo_ate_ontem, ln=1, align='L')

# ------------------------------------------------- TABELA DE REGIAO - COMPARATIVO MENSAL E ACUMULADO (DIA ANTERIOR) -------------------------------------------------
# Na virada do mês (ex: 1º mar), dados são do mês de ontem (fev); rótulos usam mes_ontem para bater com a SQL
columns_regiao_observatorio_atualizada = [
    "REGIÃO",
    f"{mes_atual}/{ano_anterior} (fechado)",
    f"{mes_ontem}/{ano_anterior} (até dia {dia_ontem})",
    f"{mes_ontem}/{ano_atual} (até dia {dia_ontem})",
    "%",
    f"Acumulado Jan a {mes_ontem} {ano_anterior} (até dia {dia_ontem})",
    f"Acumulado Jan a {mes_ontem} {ano_atual} (até dia {dia_ontem})",
    "%",
    "Índice por 100K hab."
]

columns_regiao_observatorio, rows_regiao_observatorio = resultados["Feminicídios Comparativo por Regiões"]

# Espaço antes da tabela
pdf.ln(0.5)

# Título da tabela
pdf.set_font('Arial', 'B', 12)
pdf.set_text_color(0, 0, 0)  # Preto
titulo_regiao_observatorio = f'Feminicídios por regiões comparativo dia anterior e acumulado :'
pdf.cell(0, 10, titulo_regiao_observatorio, ln=1, align='L')

col_widths_regiao_observatorio = [25, 20, 20, 20, 15, 23, 23, 15, 23]  # 9 colunas
# Cabeçalho da tabela de regiões observatório (ajustado para quebra de linha, altura uniforme)
pdf.set_font('Arial', 'B', 7)
pdf.set_fill_color(230, 230, 230)
pdf.set_draw_color(0, 0, 0)  # Preto para borda
pdf.set_text_color(0, 0, 0)  # Preto para texto

x_inicio = pdf.get_x()
y_inicio = pdf.get_y()
altura_linha = 6

# Calcula a altura máxima necessária para cada célula do cabeçalho
alturas = []
linhas_texto = []
for i, col in enumerate(columns_regiao_observatorio_atualizada):
    largura = col_widths_regiao_observatorio[i]
    # Divide o texto em linhas para a largura da célula
    linhas = pdf.multi_cell(largura, altura_linha, str(col).upper(), 0, 'C', split_only=True)
    linhas_texto.append(linhas)
    alturas.append(len(linhas) * altura_linha)
altura_max = max(alturas)

# Desenha cada célula do cabeçalho com altura máxima e texto centralizado
x = x_inicio
for i, col in enumerate(columns_regiao_observatorio_atualizada):
    largura = col_widths_regiao_observatorio[i]
    linhas = linhas_texto[i]
    n_linhas = len(linhas)
    y = y_inicio
    # Centraliza verticalmente o texto
    y_texto = y + (altura_max - n_linhas * altura_linha) / 2
    pdf.rect(x, y, largura, altura_max, 'DF')
    pdf.set_xy(x, y_texto)
    for linha in linhas:
        pdf.cell(largura, altura_linha, linha, 0, 2, 'C')
    x += largura
pdf.set_xy(x_inicio, y_inicio + altura_max)

# Dados da tabela de regiões observatório
pdf.set_font('Arial', '', 7)
pdf.set_text_color(0, 0, 0)  # Preto para texto
for row in rows_regiao_observatorio:
    for i, item in enumerate(row):
        # Coloração e formatação para as colunas de %
        if i in [4, 7]:  # Índices das colunas de %
            valor = float(item) if item is not None else 0
            texto = f"{valor:.2f}%"
            if valor > 0:
                pdf.set_fill_color(220, 20, 60)  # vermelho no background
                pdf.set_text_color(255, 255, 255)  # texto branco
            elif valor < 0:
                pdf.set_fill_color(0, 128, 0)    # verde no background
                pdf.set_text_color(255, 255, 255)  # texto branco
            else:
                pdf.set_fill_color(255, 255, 255)  # fundo branco
                pdf.set_text_color(0, 0, 0)      # texto preto
            pdf.cell(col_widths_regiao_observatorio[i], 6, texto, 1, 0, 'C', fill=True)
            pdf.set_fill_color(255, 255, 255)  # reset do background
            pdf.set_text_color(0, 0, 0)  # reset do texto
        else:
            pdf.cell(col_widths_regiao_observatorio[i], 6, safe_str(item), 1, 0, 'C')
    pdf.ln()

# Calcula e adiciona linha de TOTAL
if rows_regiao_observatorio:
    # Inicializa totais
    totais = [0] * len(rows_regiao_observatorio[0])
    
    # Calcula totais para colunas numéricas (excluindo a primeira coluna que é texto)
    for row in rows_regiao_observatorio:
        for i, item in enumerate(row):
            if i > 0:  # Pula a primeira coluna (REGIÃO)
                try:
                    if i in [4, 7]:  # Colunas de porcentagem
                        totais[i] += float(item) if item is not None else 0
                    else:  # Colunas numéricas
                        totais[i] += int(item) if item is not None else 0
                except (ValueError, TypeError):
                    pass  # Ignora valores não numéricos
    
    # Cria linha de total
    linha_total = ["GOIÁS"]
    for i in range(1, len(totais)):
        if i in [4, 7]:  # Colunas de porcentagem
            linha_total.append(f"{totais[i]:.2f}")
        else:  # Colunas numéricas
            linha_total.append(str(totais[i]))
    
    # Adiciona linha de total com formatação especial
    pdf.set_font('Arial', 'B', 7)  # Negrito para destacar
    for i, item in enumerate(linha_total):
        # Coloração e formatação para as colunas de %
        if i in [4, 7]:  # Índices das colunas de %
            valor = float(item) if item is not None else 0
            texto = f"{valor:.2f}%"
            if valor > 0:
                pdf.set_fill_color(220, 20, 60)  # vermelho no background
                pdf.set_text_color(255, 255, 255)  # texto branco
            elif valor < 0:
                pdf.set_fill_color(0, 128, 0)    # verde no background
                pdf.set_text_color(255, 255, 255)  # texto branco
            else:
                pdf.set_fill_color(255, 255, 255)  # fundo branco
                pdf.set_text_color(0, 0, 0)      # texto preto
            pdf.cell(col_widths_regiao_observatorio[i], 6, texto, 1, 0, 'C', fill=True)
            pdf.set_fill_color(255, 255, 255)  # reset do background
            pdf.set_text_color(0, 0, 0)  # reset do texto
        else:
            pdf.cell(col_widths_regiao_observatorio[i], 6, safe_str(item), 1, 0, 'C')
    pdf.ln()
    pdf.set_font('Arial', '', 7)  # Volta para fonte normal

pdf.set_font('Arial', 'I', 9)
pdf.cell(0, 8, texto_periodo_ate_ontem, ln=1, align='L')

# Adiciona uma nova página
pdf.add_page()

# ------------------------------------------------- GRAFICO COMPARATIVO POR DIA POR REGIÃO -------------------------------------------------
# Gera o gráfico comparativo de homicídios por dia por região
columns_dia_regioes, rows_dia_regioes = resultados["Feminicídios Comparativo por Dia por Regiões"]

# Título do grafico
pdf.set_font('Arial', 'B', 12)
pdf.set_text_color(0, 0, 0)
titulo_mes_regiao = f'Feminicídios por dia por Região no mês atual: {hoje.strftime("%b/%Y")}'
pdf.cell(0, 10, titulo_mes_regiao, ln=1, align='L')

# Cria o DataFrame
df_comparativo_dia = pd.DataFrame(rows_dia_regioes, columns=columns_dia_regioes)

if not df_comparativo_dia.empty:
    df_comparativo_dia['HOMICIDIOS'] = df_comparativo_dia['HOMICIDIOS'].astype(int)

    # Pivot por DATA e REGIAO_OBSERVATORIO
    df_pivot = df_comparativo_dia.pivot(index='DATA', columns='REGIAO_OBSERVATORIO', values='HOMICIDIOS').fillna(0)
    df_pivot = df_pivot.reindex(sorted(df_pivot.index, key=lambda x: int(x.split('/')[0])))

    plt.figure(figsize=(10, 1.0))
    regioes = sorted(df_pivot.columns)
    bar_width = 0.25
    x = range(len(df_pivot.index))

    for i, regiao in enumerate(regioes):
        bars = plt.bar([xi + i * bar_width for xi in x], df_pivot[regiao], width=bar_width, label=regiao)
        for bar in bars:
            height = bar.get_height()
            if height > 0:
                plt.text(
                    bar.get_x() + bar.get_width() / 2,
                    height + 0.1,
                    f'{int(height)}',
                    ha='center',
                    va='bottom',
                    fontsize=8
                )

    plt.legend(title='REGIÃO', bbox_to_anchor=(1.00, 1), loc='upper left', fontsize=8, title_fontsize=9)
    plt.ylabel('Homicídios')
    plt.yticks([])
    plt.xlabel('')
    
    plt.xticks([xi + bar_width * (len(regioes)/2 - 0.5) for xi in x], list(df_pivot.index), rotation=45)

    # Salva o gráfico com tratamento de erro
    try:
        plt.savefig(os.path.join(relatorio_dir, 'grafico_feminicidio_dia_regiao.png'), dpi=150, bbox_inches='tight')
    except Exception as e:
        print(f"Erro ao salvar gráfico: {e}")
        try:
            plt.savefig(os.path.join(relatorio_dir, 'grafico_feminicidio_dia_regiao.png'), format='png', dpi=100)
        except Exception as e2:
            print(f"Erro ao salvar com configurações básicas: {e2}")
            plt.figure(figsize=(10, 3.0))
            plt.text(0.5, 0.5, 'Gráfico não disponível', ha='center', va='center', transform=plt.gca().transAxes)
            plt.savefig(os.path.join(relatorio_dir, 'grafico_feminicidio_dia_regiao.png'), format='png', dpi=100)
    plt.close()

# Adiciona o gráfico ao PDF apenas se foi gerado (evita FPDF "Not a PNG file" com arquivo antigo)
grafico_path = os.path.join(relatorio_dir, 'grafico_feminicidio_dia_regiao.png')
if not df_comparativo_dia.empty and os.path.exists(grafico_path):
    try:
        pdf.image(grafico_path, x=5, w=200)
    except Exception as e:
        print(f"Erro ao inserir gráfico dia região: {e}")
        pdf.set_font('Arial', 'I', 10)
        pdf.cell(0, 8, 'Gráfico não disponível', ln=1, align='C')
else:
    if df_comparativo_dia.empty:
        sem_dados_path = os.path.join(relatorio_dir, 'sem_dados.png')
        if os.path.exists(sem_dados_path):
            try:
                w_img = 80
                x_centro = (210 - w_img) / 2
                pdf.image(sem_dados_path, x=x_centro, w=w_img)
            except Exception:
                pdf.set_font('Arial', 'I', 10)
                pdf.cell(0, 8, 'Não há valores registrados', ln=1, align='C')
        else:
            pdf.set_font('Arial', 'I', 10)
            pdf.cell(0, 8, 'Não há valores registrados', ln=1, align='C')
    else:
        pdf.set_font('Arial', 'I', 10)
        pdf.cell(0, 8, 'Gráfico não disponível', ln=1, align='C')
pdf.set_font('Arial', 'I', 9)
pdf.cell(0, 8, texto_periodo_ate_ontem, ln=1, align='L')

# ------------------------------------------------- GRAFICO COMPARATIVO POR MES POR REGIÃO -------------------------------------------------
# Gera o gráfico comparativo de homicídios por mês por região
columns_mes_regioes, rows_mes_regioes = resultados["Feminicídios Comparativo por Mes por Regiões"]

# Título do grafico
pdf.set_font('Arial', 'B', 12)
pdf.set_text_color(0, 0, 0)
titulo_mes_regiao = f'Feminicídios - Mês a mês por Região no ano {hoje.year}:'
pdf.cell(0, 10, titulo_mes_regiao, ln=1, align='L')

# Cria o DataFrame
df_comparativo_mes = pd.DataFrame(rows_mes_regioes, columns=columns_mes_regioes)

if not df_comparativo_mes.empty:
    df_comparativo_mes['HOMICIDIOS'] = df_comparativo_mes['HOMICIDIOS'].astype(int)
    df_comparativo_mes['NUMERO_MES'] = df_comparativo_mes['NUMERO_MES'].astype(int)

    # Pivot por MES e REGIAO_OBSERVATORIO
    df_pivot_mes = df_comparativo_mes.pivot(index='MES', columns='REGIAO_OBSERVATORIO', values='HOMICIDIOS').fillna(0)
    
    # Ordena por número do mês
    df_pivot_mes = df_pivot_mes.reindex(sorted(df_pivot_mes.index, key=lambda x: df_comparativo_mes[df_comparativo_mes['MES'] == x]['NUMERO_MES'].iloc[0]))

    #plt.figure(figsize=(10, 3.0))
    
    # Cria o gráfico de barras empilhadas
    ax = df_pivot_mes.plot(kind='bar', stacked=True, width=0.7, figsize=(10, 2.0))  
    
    # Adiciona os valores nas barras
    for c in ax.containers:
        ax.bar_label(c, label_type='center', fontsize=8)
    
    # Adiciona os totais no topo das barras
    totais = df_pivot_mes.sum(axis=1)
    for i, total in enumerate(totais):
        if total > 0:
            ax.text(i, total + 1, f'{int(total)}', ha='center', va='bottom', fontsize=8)
    
    # Adiciona fundo esmairecido por região conectando as barras
    bar_width = 0.7  # Largura das barras
    x_positions = np.arange(len(df_pivot_mes.index))
    
    # Para cada região, cria áreas esmairecidas
    for i, regiao in enumerate(df_pivot_mes.columns):
        # Valores da região específica
        valores_regiao = df_pivot_mes[regiao].values
        
        # Calcula a base para empilhamento (soma das regiões anteriores)
        base = np.zeros_like(valores_regiao)
        for j in range(i):
            valores_anterior = df_pivot_mes[df_pivot_mes.columns[j]].values
            base += valores_anterior
        
        # Obtém a cor da região das barras (padrão seaborn)
        cor_regiao = ax.containers[i][0].get_facecolor()
        
        # Cria áreas esmairecidas entre cada par de barras consecutivas
        for k in range(len(x_positions) - 1):
            # Ponta direita da barra atual
            x1 = x_positions[k] + bar_width/2
            y1 = base[k] + valores_regiao[k]
            
            # Ponta esquerda da próxima barra
            x2 = x_positions[k+1] - bar_width/2
            y2 = base[k+1] + valores_regiao[k+1]
            
            # Cria pontos suavizados entre os dois pontos
            x_area = np.linspace(x1, x2, 50)
            y_area = np.linspace(y1, y2, 50)
            
            # Adiciona uma pequena ondulação
            wave_amplitude = max(valores_regiao) * 0.01 if max(valores_regiao) > 0 else 0.3
            wave = wave_amplitude * np.sin(np.linspace(0, np.pi, 50))
            y_area += wave
            
            # Desenha apenas a área esmairecida preenchendo todo o espaço entre as barras
            base_area = np.linspace(base[k], base[k+1], 50)
            ax.fill_between(x_area, base_area, y_area, color=cor_regiao, alpha=0.25, zorder=1)
    
    plt.legend(title='REGIÃO', bbox_to_anchor=(1.00, 1), loc='upper left', fontsize=8, title_fontsize=9)
    plt.ylabel('Homicídios')
    plt.yticks([])
    plt.xlabel('')
    plt.xticks(range(len(df_pivot_mes.index)), list(df_pivot_mes.index), rotation=0)
    #plt.tight_layout()   
    
    # Salva o gráfico com tratamento de erro
    try:
        plt.savefig(os.path.join(relatorio_dir, 'grafico_feminicidio_mes_regiao.png'), dpi=150, bbox_inches='tight')
    except Exception as e:
        print(f"Erro ao salvar gráfico: {e}")
        try:
            plt.savefig(os.path.join(relatorio_dir, 'grafico_feminicidio_mes_regiao.png'), format='png', dpi=100)
        except Exception as e2:
            print(f"Erro ao salvar com configurações básicas: {e2}")
            plt.figure(figsize=(10, 3.0))
            plt.text(0.5, 0.5, 'Gráfico não disponível', ha='center', va='center', transform=plt.gca().transAxes)
            plt.savefig(os.path.join(relatorio_dir, 'grafico_feminicidio_mes_regiao.png'), format='png', dpi=100)
    plt.close()

# Adiciona o DataFrame ao PDF
# Verifica se o arquivo existe antes de adicionar ao PDF
grafico_mes_regiao_path = os.path.join(relatorio_dir, 'grafico_feminicidio_mes_regiao.png')
if os.path.exists(grafico_mes_regiao_path):
    pdf.image(grafico_mes_regiao_path, x=5, w=200)
else:
    pdf.set_font('Arial', 'I', 10)
    pdf.cell(0, 8, 'Gráfico não disponível', ln=1, align='C')
pdf.set_font('Arial', 'I', 9)
pdf.cell(0, 8, texto_periodo_ate_ontem, ln=1, align='L')

# ------------------------------------------------- TABELA COMPARATIVO POR MES POR REGIÃO -------------------------------------------------
# Gera tabela com dados do gráfico comparativo de homicídios por mês por região

# Título da tabela
pdf.set_font('Arial', 'B', 12)
pdf.set_text_color(0, 0, 0)
titulo_tabela = f'Feminicídios - Mês a mês por Região no ano {hoje.year}:'
pdf.cell(0, 10, titulo_tabela, ln=1, align='L')

# Cria a tabela com os dados
if not df_comparativo_mes.empty:
    # Pivot para criar a tabela
    df_tabela = df_comparativo_mes.pivot(index='REGIAO_OBSERVATORIO', columns='MES', values='HOMICIDIOS').fillna(0)
    
    # Ordena por número do mês
    df_tabela = df_tabela.reindex(sorted(df_tabela.columns, key=lambda x: df_comparativo_mes[df_comparativo_mes['MES'] == x]['NUMERO_MES'].iloc[0]), axis=1)
    
    # Adiciona linha de totais
    totais_mes = df_tabela.sum()
    df_tabela.loc['Totais (n. vítimas)'] = totais_mes
    
    # Configurações da tabela - Ajustadas para A4
    largura_total = 190  # Largura disponível na página A4
    largura_regiao = 25  # Largura da coluna região (alinhado ao padrão das demais tabelas)
    largura_disponivel = largura_total - largura_regiao
    num_meses = len(df_tabela.columns)
    col_width = largura_disponivel / num_meses if num_meses > 0 else largura_disponivel
    
    row_height = 5
    header_height = 5
    
    # Cabeçalho da tabela
    pdf.set_font('Arial', 'B', 7)
    pdf.set_fill_color(230, 230, 230)
    pdf.set_draw_color(0, 0, 0)
    pdf.set_text_color(0, 0, 0)
    
    # Cabeçalho - Região
    pdf.cell(largura_regiao, header_height, 'Região', 1, 0, 'C', fill=True)
    
    # Cabeçalho - Meses
    for mes in df_tabela.columns:
        pdf.cell(col_width, header_height, str(mes), 1, 0, 'C', fill=True)
    pdf.ln()
    
    # Linhas de dados
    pdf.set_font('Arial', '', 7)
    for regiao in df_tabela.index:
        # Nome da região
        pdf.cell(largura_regiao, row_height, str(regiao), 1, 0, 'L')
        
        # Valores dos meses
        for mes in df_tabela.columns:
            valor = df_tabela.loc[regiao, mes]
            pdf.cell(col_width, row_height, str(int(valor)), 1, 0, 'C')
        pdf.ln()

pdf.set_font('Arial', 'I', 9)
pdf.cell(0, 8, texto_periodo_ate_ontem, ln=1, align='L')

# ------------------------------------------------- GRAFICO COMPARATIVO POR SEMANA POR REGIÃO -------------------------------------------------
# Gera o gráfico comparativo de homicídios por semana por região
columns_semana_regioes, rows_semana_regioes = resultados["Feminicídios Comparativo por Semana por Regiões"]

# Título do grafico
pdf.set_font('Arial', 'B', 12)
pdf.set_text_color(0, 0, 0)
titulo_semana_regiao = f'Homicídios - dias da semana por Região no ano {hoje.year}:'    
pdf.cell(0, 10, titulo_semana_regiao, ln=1, align='L')

# Cria o DataFrame
df_comparativo_semana = pd.DataFrame(rows_semana_regioes, columns=columns_semana_regioes)

if not df_comparativo_semana.empty:
    df_comparativo_semana['HOMICIDIOS'] = df_comparativo_semana['HOMICIDIOS'].astype(int)
    df_comparativo_semana['NUMERO_DIA_SEMANA'] = df_comparativo_semana['NUMERO_DIA_SEMANA'].astype(int)
    
    # Pivot por DIA_SEMANA e REGIAO_OBSERVATORIO
    df_pivot_semana = df_comparativo_semana.pivot(index='DIA_SEMANA', columns='REGIAO_OBSERVATORIO', values='HOMICIDIOS').fillna(0)
    
    # Ordena os dias da semana corretamente (domingo=1, segunda=2, ..., sábado=7)
    df_pivot_semana = df_pivot_semana.reindex(sorted(df_pivot_semana.index, key=lambda x: df_comparativo_semana[df_comparativo_semana['DIA_SEMANA'] == x]['NUMERO_DIA_SEMANA'].iloc[0]))
    
    # Inverte a ordem para que domingo apareça no topo do gráfico horizontal
    df_pivot_semana = df_pivot_semana.iloc[::-1]

    plt.figure(figsize=(10, 2.0))
    
    # Cria o gráfico de barras empilhadas
    ax = df_pivot_semana.plot(kind='barh', stacked=True, width=0.7, figsize=(10, 3.0))
    
    # Adiciona os valores nas barras
    for c in ax.containers:
        ax.bar_label(c, label_type='center', fontsize=8)
    
    # Adiciona os totais no final das barras
    totais = df_pivot_semana.sum(axis=1)
    for i, total in enumerate(totais):
        if total > 0:
            ax.text(total + 1, i, f'{int(total)}', ha='left', va='center', fontsize=8)
    
    plt.legend(title='REGIÃO', bbox_to_anchor=(1.00, 1), loc='upper left', fontsize=8, title_fontsize=9)
    plt.ylabel('Dias da Semana')
    plt.yticks(range(len(df_pivot_semana.index)), df_pivot_semana.index, fontsize=9)
    plt.xticks([]) 
    
    
    # Salva o gráfico com tratamento de erro
    try:
        plt.savefig(os.path.join(relatorio_dir, 'grafico_feminicidio_semana_regiao.png'), dpi=150, bbox_inches='tight')
    except Exception as e:
        print(f"Erro ao salvar gráfico: {e}")
        try:
            plt.savefig(os.path.join(relatorio_dir, 'grafico_feminicidio_semana_regiao.png'), format='png', dpi=100)
        except Exception as e2:
            print(f"Erro ao salvar com configurações básicas: {e2}")
            plt.figure(figsize=(10, 3.0))
            plt.text(0.5, 0.5, 'Gráfico não disponível', ha='center', va='center', transform=plt.gca().transAxes)
            plt.savefig(os.path.join(relatorio_dir, 'grafico_feminicidio_semana_regiao.png'), format='png', dpi=100)
    plt.close()

# Adiciona o DataFrame ao PDF
# Verifica se o arquivo existe antes de adicionar ao PDF
grafico_semana_regiao_path = os.path.join(relatorio_dir, 'grafico_feminicidio_semana_regiao.png')
if os.path.exists(grafico_semana_regiao_path):
    pdf.image(grafico_semana_regiao_path, x=5, w=200)
else:
    pdf.set_font('Arial', 'I', 10)
    pdf.cell(0, 8, 'Gráfico não disponível', ln=1, align='C')
pdf.set_font('Arial', 'I', 9)
pdf.cell(0, 8, texto_periodo_ate_ontem, ln=1, align='L')

# ------------------------------------------------- GRAFICO DE HOMICÍDIOS EM PRESIDIOS -------------------------------------------------
# Gera tabela com dados do gráfico comparativo de homicídios por mês por região
columns_grafico_presidios, rows_grafico_presidios = resultados["Feminicídios em Presídios"]

# Título da tabela
pdf.set_font('Arial', 'B', 12)
pdf.set_text_color(0, 0, 0)
titulo_tabela = f'Feminicídios - Presídios'
pdf.cell(0, 10, titulo_tabela, ln=1, align='L')

# Cria o DataFrame
df_grafico_presidios = pd.DataFrame(rows_grafico_presidios, columns=columns_grafico_presidios)

# Cria a tabela com os dados
if not df_grafico_presidios.empty:
    
    # Agrupa por município e soma os totais
    df_agrupado = df_grafico_presidios.groupby('MUNICIPIO_NOME')['TOTAL'].sum().reset_index()
    
    # Ordena por total de homicídios em ordem decrescente
    df_agrupado = df_agrupado.sort_values('TOTAL', ascending=False)
    
    # Calcula o total geral
    total_geral = df_agrupado['TOTAL'].sum()
    
    # Cria o gráfico de barras horizontais
    plt.figure(figsize=(10, max(1.2, len(df_agrupado) * 0.35)))
    
    # Cria o gráfico de barras horizontais (mais fina)
    bars = plt.barh(df_agrupado['MUNICIPIO_NOME'],df_agrupado['TOTAL'], height=0.4,color='steelblue',alpha=0.8 )

    # Garante margem vertical para não ocupar toda a altura quando houver poucas barras
    ax = plt.gca()
    num_barras = len(df_agrupado)
    pad = 0.6
    ax.set_ylim(-0.5 - pad, (num_barras - 1) + 0.5 + pad)
    
    # Adiciona os valores nas barras
    for i, bar in enumerate(bars):
        width = bar.get_width()
        plt.text(width + 0.01, bar.get_y() + bar.get_height()/2, 
                f'{int(width)}', ha='left', va='center', fontweight='bold')
    
    # Configurações do gráfico
    plt.ylabel('Município')
    plt.xticks([])
    
    # Salva o gráfico com tratamento de erro
    try:
        plt.savefig(os.path.join(relatorio_dir, 'grafico_feminicidio_presidios.png'), dpi=150, bbox_inches='tight')
    except Exception as e:
        print(f"Erro ao salvar gráfico: {e}")
        try:
            plt.savefig(os.path.join(relatorio_dir, 'grafico_feminicidio_presidios.png'), format='png', dpi=100)
        except Exception as e2:
            print(f"Erro ao salvar com configurações básicas: {e2}")
            plt.figure(figsize=(10, 3.0))
            plt.text(0.5, 0.5, 'Gráfico não disponível', ha='center', va='center', transform=plt.gca().transAxes)
            plt.savefig(os.path.join(relatorio_dir, 'grafico_feminicidio_presidios.png'), format='png', dpi=100)
    plt.close()

    # Adiciona o gráfico ao PDF
    # Verifica se o arquivo existe antes de adicionar ao PDF
    grafico_presidios_path = os.path.join(relatorio_dir, 'grafico_feminicidio_presidios.png')
    if os.path.exists(grafico_presidios_path):
        pdf.image(grafico_presidios_path, x=5, w=200)
    else:
        pdf.set_font('Arial', 'I', 10)
        pdf.cell(0, 8, 'Gráfico não disponível', ln=1, align='C')
else:
    # Sem dados: imagem pequena e centralizada para não quebrar a página
    sem_dados_path = os.path.join(relatorio_dir, 'sem_dados.png')
    try:
        fig, ax = plt.subplots(figsize=(4, 0.8))
        ax.axis('off')
        ax.text(0.5, 0.5, 'Não há valores registrados', ha='center', va='center', fontsize=11, color='#666666')
        plt.savefig(sem_dados_path, dpi=150, bbox_inches='tight', facecolor='white')
        plt.close()
    except Exception as e:
        print(f"Erro ao gerar imagem sem_dados: {e}")
    if os.path.exists(sem_dados_path):
        try:
            w_img = 80
            x_centro = (210 - w_img) / 2
            pdf.image(sem_dados_path, x=x_centro, w=w_img)
        except Exception:
            pdf.set_font('Arial', 'I', 10)
            pdf.cell(0, 8, 'Não há valores registrados', ln=1, align='C')
    else:
        pdf.set_font('Arial', 'I', 10)
        pdf.cell(0, 8, 'Não há valores registrados', ln=1, align='C')

pdf.set_font('Arial', 'I', 9)
pdf.cell(0, 8, texto_periodo_ate_ontem, ln=1, align='L')

# Adiciona uma nova página
pdf.add_page()

# ------------------------------------------------- TABELA DE FEMINICÍDIOS POR MUNICIPIOS TOP 20 (DIA ANTERIOR) -------------------------------------------------
# Rótulos com mes_ontem para virada do mês
columns_municipio_top20_atualizada = [
    "REGIÃO",
    f"{mes_atual}/{ano_anterior} (fechado)",
    f"{mes_ontem}/{ano_anterior} (até dia {dia_ontem})",
    f"{mes_ontem}/{ano_atual} (até dia {dia_ontem})",
    "%",
    f"Acumulado Jan a {mes_ontem} {ano_anterior} (até dia {dia_ontem})",
    f"Acumulado Jan a {mes_ontem} {ano_atual} (até dia {dia_ontem})",
    "%",
    "Índice por 100K hab."
]

columns_municipio_top20, rows_municipio_top20 = resultados["Feminicídios Comparativo por Município Top 20"]

# Título da tabela
pdf.set_font('Arial', 'B', 12)
pdf.set_text_color(0, 0, 0)  # Preto
titulo_municipio_top20 = f'Feminicídios por municípios - comparativo dia anterior e acumulado :'
pdf.cell(0, 10, titulo_municipio_top20, ln=1, align='L')

col_widths_municipio_top20 = [60, 17, 17, 17, 12, 22, 22, 12, 15]  # 9 colunas
# Cabeçalho da tabela de regiões observatório (ajustado para quebra de linha, altura uniforme)
pdf.set_font('Arial', 'B', 7)
pdf.set_fill_color(230, 230, 230)
pdf.set_draw_color(0, 0, 0)  # Preto para borda
pdf.set_text_color(0, 0, 0)  # Preto para texto

# Garante início na margem esquerda
pdf.set_x(pdf.l_margin)
x_inicio = pdf.get_x()
y_inicio = pdf.get_y()
altura_linha = 5

# Pré-calcula quebras e alturas
alturas, linhas_texto = [], []
for i, col in enumerate(columns_municipio_top20_atualizada):
    largura = col_widths_municipio_top20[i]
    linhas = pdf.multi_cell(largura, altura_linha, str(col).upper(), 0, 'C', split_only=True)
    linhas_texto.append(linhas)
    alturas.append(len(linhas) * altura_linha)
altura_max = max(alturas)
# --- se não couber, vá para nova página antes de desenhar ---
if y_inicio + altura_max > pdf.page_break_trigger:
    pdf.add_page()
    pdf.set_x(pdf.l_margin)
    x_inicio = pdf.get_x()
    y_inicio = pdf.get_y()

# Desenha o cabeçalho sem permitir que o FPDF quebre a página no meio
prev_auto = pdf.auto_page_break
prev_margin = getattr(pdf, 'b_margin', pdf.b_margin if hasattr(pdf, 'b_margin') else 0)
pdf.set_auto_page_break(False)

x = x_inicio
y = y_inicio

for i, _ in enumerate(columns_municipio_top20_atualizada):
    largura = col_widths_municipio_top20[i]
    linhas = linhas_texto[i]
    n_linhas = len(linhas)

    y_texto = y + (altura_max - n_linhas * altura_linha) / 2
    pdf.rect(x, y, largura, altura_max, 'DF')

    # escreve as linhas sem quebrar para a margem (sem ln=2)
    y_atual = y_texto
    for linha in linhas:
        pdf.set_xy(x, y_atual)
        pdf.cell(largura, altura_linha, linha, 0, 0, 'C')
        y_atual += altura_linha

    x += largura

# posiciona o cursor logo abaixo do cabeçalho
pdf.set_xy(pdf.l_margin, y_inicio + altura_max)

# Restaura o autobrake
pdf.set_auto_page_break(prev_auto, prev_margin)

# Dados da tabela de regiões observatório
pdf.set_font('Arial', '', 7)
pdf.set_text_color(0, 0, 0)  # Preto para texto

# Adiciona zebragem (alternância de cores de fundo)
for idx, row in enumerate(rows_municipio_top20):
    # Alterna a cor de fundo: linhas pares = branco, linhas ímpares = cinza claro
    if idx % 2 == 0:
        pdf.set_fill_color(255, 255, 255)  # Branco
    else:
        pdf.set_fill_color(240, 240, 245)  # Cinza claro
    
    for i, item in enumerate(row):
        # Coloração e formatação para as colunas de %
        if i in [4, 7]:  # Índices das colunas de %
            valor = float(item) if item is not None else 0
            texto = f"{valor:.2f}%"
            if valor > 0:
                pdf.set_fill_color(220, 20, 60)  # vermelho no background
                pdf.set_text_color(255, 255, 255)  # texto branco
            elif valor < 0:
                pdf.set_fill_color(0, 128, 0)    # verde no background
                pdf.set_text_color(255, 255, 255)  # texto branco
            else:
                pdf.set_fill_color(255, 255, 255)  # fundo branco
                pdf.set_text_color(0, 0, 0)      # texto preto
            pdf.cell(col_widths_municipio_top20[i], 6, texto, 1, 0, 'C', fill=True)
            pdf.set_fill_color(255, 255, 255)  # reset do background
            pdf.set_text_color(0, 0, 0)  # reset do texto
        else:
            pdf.cell(col_widths_municipio_top20[i], 6, safe_str(item), 1, 0, 'C', fill=True)
    pdf.ln()

pdf.set_font('Arial', 'I', 9)
pdf.cell(0, 8, texto_periodo_ate_ontem, ln=1, align='L')

# Adiciona uma nova página
pdf.add_page()
# ------------------------------------------------- TABELA DE FEMINICÍDIOS POR RISP (DIA ANTERIOR) -------------------------------------------------
# Rótulos com mes_ontem para virada do mês
columns_risp_atualizada = [
    "RISP",
    f"{mes_atual}/{ano_anterior} (fechado)",
    f"{mes_ontem}/{ano_anterior} (até dia {dia_ontem})",
    f"{mes_ontem}/{ano_atual} (até dia {dia_ontem})",
    "%",
    f"Acumulado Jan a {mes_ontem} {ano_anterior} (até dia {dia_ontem})",
    f"Acumulado Jan a {mes_ontem} {ano_atual} (até dia {dia_ontem})",
    "%",
    "Índice por 100K hab."
]

columns_risp, rows_risp = resultados["Feminicídios Comparativo por Risp"]

# Espaço antes da tabela
pdf.ln(1)

# Título da tabela
pdf.set_font('Arial', 'B', 12)
pdf.set_text_color(0, 0, 0)  # Preto
titulo_risp = f'Feminicídios por Risp - comparativo dia anterior e acumulado :'
pdf.cell(0, 10, titulo_risp, ln=1, align='L')

col_widths_risp = [60, 17, 17, 17, 12, 22, 22, 12, 15]  

# Cabeçalho da tabela de Risp (ajustado para quebra de linha, altura uniforme)
pdf.set_font('Arial', 'B', 7)
pdf.set_fill_color(230, 230, 230)
pdf.set_draw_color(0, 0, 0)  # Preto para borda
pdf.set_text_color(0, 0, 0)  # Preto para texto

# Garante início na margem esquerda
pdf.set_x(pdf.l_margin)
x_inicio = pdf.get_x()
y_inicio = pdf.get_y()
altura_linha = 5

# Pré-calcula quebras e alturas
alturas, linhas_texto = [], []
for i, col in enumerate(columns_risp_atualizada):
    largura = col_widths_risp[i]
    linhas = pdf.multi_cell(largura, altura_linha, str(col).upper(), 0, 'C', split_only=True)
    linhas_texto.append(linhas)
    alturas.append(len(linhas) * altura_linha)
altura_max = max(alturas)
# --- se não couber, vá para nova página antes de desenhar ---
if y_inicio + altura_max > pdf.page_break_trigger:
    pdf.add_page()
    pdf.set_x(pdf.l_margin)
    x_inicio = pdf.get_x()
    y_inicio = pdf.get_y()

# Desenha o cabeçalho sem permitir que o FPDF quebre a página no meio
prev_auto = pdf.auto_page_break
prev_margin = getattr(pdf, 'b_margin', pdf.b_margin if hasattr(pdf, 'b_margin') else 0)
pdf.set_auto_page_break(False)

x = x_inicio
y = y_inicio

for i, _ in enumerate(columns_risp_atualizada):
    largura = col_widths_risp[i]
    linhas = linhas_texto[i]
    n_linhas = len(linhas)

    y_texto = y + (altura_max - n_linhas * altura_linha) / 2
    pdf.rect(x, y, largura, altura_max, 'DF')

    # escreve as linhas sem quebrar para a margem (sem ln=2)
    y_atual = y_texto
    for linha in linhas:
        pdf.set_xy(x, y_atual)
        pdf.cell(largura, altura_linha, linha, 0, 0, 'C')
        y_atual += altura_linha

    x += largura

# posiciona o cursor logo abaixo do cabeçalho
pdf.set_xy(pdf.l_margin, y_inicio + altura_max)

# Restaura o autobrake
pdf.set_auto_page_break(prev_auto, prev_margin)

# Dados da tabela de regiões observatório
pdf.set_font('Arial', '', 7)
pdf.set_text_color(0, 0, 0)  # Preto para texto

# Adiciona zebragem (alternância de cores de fundo)
for idx, row in enumerate(rows_risp):
    # Alterna a cor de fundo: linhas pares = branco, linhas ímpares = cinza claro
    if idx % 2 == 0:
        pdf.set_fill_color(255, 255, 255)  # Branco
    else:
        pdf.set_fill_color(240, 240, 245)  # Cinza claro
    
    for i, item in enumerate(row):
        # Coloração e formatação para as colunas de %
        if i in [4, 7]:  # Índices das colunas de %
            valor = float(item) if item is not None else 0
            texto = f"{valor:.2f}%"
            if valor > 0:
                pdf.set_fill_color(220, 20, 60)  # vermelho no background
                pdf.set_text_color(255, 255, 255)  # texto branco
            elif valor < 0:
                pdf.set_fill_color(0, 128, 0)    # verde no background
                pdf.set_text_color(255, 255, 255)  # texto branco
            else:
                pdf.set_fill_color(255, 255, 255)  # fundo branco
                pdf.set_text_color(0, 0, 0)      # texto preto
            pdf.cell(col_widths_risp[i], 6, texto, 1, 0, 'C', fill=True)
            pdf.set_fill_color(255, 255, 255)  # reset do background
            pdf.set_text_color(0, 0, 0)  # reset do texto
        else:
            pdf.cell(col_widths_risp[i], 6, safe_str(item), 1, 0, 'C', fill=True)
    pdf.ln()

pdf.set_font('Arial', 'I', 9)
pdf.cell(0, 8, texto_periodo_ate_ontem, ln=1, align='L')

# Adiciona uma nova página
pdf.add_page()
# ------------------------------------------------- TABELA DE FEMINICÍDIOS POR AISP (DIA ANTERIOR) -------------------------------------------------
# Rótulos com mes_ontem para virada do mês
columns_aisp_atualizada = [
    "AISP",
    f"{mes_atual}/{ano_anterior} (fechado)",
    f"{mes_ontem}/{ano_anterior} (até dia {dia_ontem})",
    f"{mes_ontem}/{ano_atual} (até dia {dia_ontem})",
    "%",
    f"Acumulado Jan a {mes_ontem} {ano_anterior} (até dia {dia_ontem})",
    f"Acumulado Jan a {mes_ontem} {ano_atual} (até dia {dia_ontem})",
    "%",
    "Índice por 100K hab."
]

columns_aisp, rows_aisp = resultados["Feminicídios Comparativo por Aisp"]

# Espaço antes da tabela
pdf.ln(1)

# Título da tabela
pdf.set_font('Arial', 'B', 12)
pdf.set_text_color(0, 0, 0)  # Preto
titulo_aisp = f'Feminicídios por Aisp - comparativo dia anterior e acumulado :'
pdf.cell(0, 10, titulo_aisp, ln=1, align='L')

col_widths_aisp = [60, 17, 17, 17, 12, 22, 22, 12, 15]  # 9 colunas
# Cabeçalho da tabela de Aisp (ajustado para quebra de linha, altura uniforme)
pdf.set_font('Arial', 'B', 7)
pdf.set_fill_color(230, 230, 230)
pdf.set_draw_color(0, 0, 0)  # Preto para borda
pdf.set_text_color(0, 0, 0)  # Preto para texto

# Garante início na margem esquerda
pdf.set_x(pdf.l_margin)
x_inicio = pdf.get_x()
y_inicio = pdf.get_y()
altura_linha = 5

# Pré-calcula quebras e alturas
alturas, linhas_texto = [], []
for i, col in enumerate(columns_aisp_atualizada):
    largura = col_widths_aisp[i]
    linhas = pdf.multi_cell(largura, altura_linha, str(col).upper(), 0, 'C', split_only=True)
    linhas_texto.append(linhas)
    alturas.append(len(linhas) * altura_linha)
altura_max = max(alturas)
# --- se não couber, vá para nova página antes de desenhar ---
if y_inicio + altura_max > pdf.page_break_trigger:
    pdf.add_page()
    pdf.set_x(pdf.l_margin)
    x_inicio = pdf.get_x()
    y_inicio = pdf.get_y()  

# Desenha o cabeçalho sem permitir que o FPDF quebre a página no meio
prev_auto = pdf.auto_page_break
prev_margin = getattr(pdf, 'b_margin', pdf.b_margin if hasattr(pdf, 'b_margin') else 0)
pdf.set_auto_page_break(False)

x = x_inicio
y = y_inicio

for i, _ in enumerate(columns_aisp_atualizada):
    largura = col_widths_aisp[i]
    linhas = linhas_texto[i]
    n_linhas = len(linhas)

    y_texto = y + (altura_max - n_linhas * altura_linha) / 2
    pdf.rect(x, y, largura, altura_max, 'DF') 

    # escreve as linhas sem quebrar para a margem (sem ln=2)
    y_atual = y_texto
    for linha in linhas:
        pdf.set_xy(x, y_atual)
        pdf.cell(largura, altura_linha, linha, 0, 0, 'C')
        y_atual += altura_linha

    x += largura  

# posiciona o cursor logo abaixo do cabeçalho
pdf.set_xy(pdf.l_margin, y_inicio + altura_max)

# Restaura o autobrake
pdf.set_auto_page_break(prev_auto, prev_margin) 

# Dados da tabela de regiões observatório
pdf.set_font('Arial', '', 7)
pdf.set_text_color(0, 0, 0)  # Preto para texto

# Adiciona zebragem (alternância de cores de fundo)
for idx, row in enumerate(rows_aisp):
    # Alterna a cor de fundo: linhas pares = branco, linhas ímpares = cinza claro
    if idx % 2 == 0:
        pdf.set_fill_color(255, 255, 255)  # Branco
    else:
        pdf.set_fill_color(240, 240, 245)  # Cinza claro
    
    for i, item in enumerate(row):
        # Coloração e formatação para as colunas de %
        if i in [4, 7]:  # Índices das colunas de %
            valor = float(item) if item is not None else 0
            texto = f"{valor:.2f}%" 
            if valor > 0:
                pdf.set_fill_color(220, 20, 60)  # vermelho no background
                pdf.set_text_color(255, 255, 255)  # texto branco
            elif valor < 0:
                pdf.set_fill_color(0, 128, 0)    # verde no background
                pdf.set_text_color(255, 255, 255)  # texto branco
            else:
                pdf.set_fill_color(255, 255, 255)  # fundo branco
                pdf.set_text_color(0, 0, 0)      # texto preto
            pdf.cell(col_widths_aisp[i], 6, texto, 1, 0, 'C', fill=True)
            pdf.set_fill_color(255, 255, 255)  # reset do background
            pdf.set_text_color(0, 0, 0)  # reset do texto
        else:
            pdf.cell(col_widths_aisp[i], 6, safe_str(item), 1, 0, 'C', fill=True)
    pdf.ln()

pdf.set_font('Arial', 'I', 9)
pdf.cell(0, 8, texto_periodo_ate_ontem, ln=1, align='L')

# ------------------------------------------------- SALVANDO O PDF -------------------------------------------------

# --- ATRIBUIÇÃO DOS TEMPOS DE EXECUÇÃO PARA O RODAPÉ ---
# Calcula o tempo total de execução
tempo_total_segundos = sum(tempos_execucao.values())
horas = int(tempo_total_segundos // 3600)
minutos = int((tempo_total_segundos % 3600) // 60)
segundos = int(tempo_total_segundos % 60)
tempo_total_formatado = f"{horas:02d}:{minutos:02d}:{segundos:02d}"

# Adiciona linha com tempo total
pdf.set_font('Arial', 'B', 7)  # Negrito para destacar o total
pdf.cell(0, 8, f'TEMPO TOTAL DE EXECUÇÃO DAS CONSULTAS: {tempo_total_formatado}', ln=1, align='L')
pdf.set_font('Arial', '', 6)  # Volta para fonte normal

# --- Antes de salvar, defina os tempos: ---
caminho_pdf = os.path.join(PROJECT_ROOT, 'pysql', 'reports_pysql', 'relatorio_feminicidios.pdf')
pdf.output(caminho_pdf)
print(f"PDF salvo: {caminho_pdf}", flush=True)

# Salva os tempos de execução para uso futuro
salvar_tempos_execucao(tempos_execucao)

cursor.close()
conn.close()
print("Concluído.", flush=True)