import os
import oracledb as cx_Oracle
from fpdf import FPDF
# Carregar variáveis do .env (se usar python-dotenv)
from dotenv import load_dotenv
load_dotenv()
import time
from tqdm import tqdm
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

class PDFComRodape(FPDF):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tempo_homicidio = ""
        self.tempo_feminicidio = ""
        self.tempo_municipio = ""
        self.tempo_homicidio_comparativo_dois_anos = ""

    def footer(self):
        self.set_y(-20)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(80, 80, 80)
        if self.tempo_homicidio and self.tempo_feminicidio:
            self.cell(0, 8, f'Tempo de execução da consulta Homicídio: {self.tempo_homicidio} segundos', ln=1, align='C')
            self.cell(0, 8, f'Tempo de execução da consulta Feminicídio: {self.tempo_feminicidio} segundos', ln=1, align='C')
        if self.tempo_municipio:
            self.cell(0, 8, f'Tempo de execução da consulta por município: {self.tempo_municipio} segundos', ln=1, align='C')
        if self.tempo_homicidio_comparativo_dois_anos:
            self.cell(0, 8, f'Tempo de execução da consulta tempo_homicidio_comparativo_dois_anos: {self.tempo_homicidio_comparativo_dois_anos} segundos', ln=1, align='C')

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

# --- BLOCO DE QUERIES SQL ---
# Query principal de homicídio
query_homicidio = '''
SELECT
  COUNT(DISTINCT CASE WHEN TRUNC(oc.datafato) = TRUNC(SYSDATE) THEN pes.id END) AS homicidios_hoje,
  COUNT(DISTINCT CASE WHEN TRUNC(oc.datafato) = TRUNC(SYSDATE-1) THEN pes.id END) AS homicidios_ontem,
  COUNT(DISTINCT CASE WHEN EXTRACT(MONTH FROM oc.datafato) = EXTRACT(MONTH FROM SYSDATE) AND EXTRACT(YEAR FROM oc.datafato) = EXTRACT(YEAR FROM SYSDATE) THEN pes.id END) AS homicidios_mes,
  COUNT(DISTINCT CASE WHEN EXTRACT(YEAR FROM oc.datafato) = EXTRACT(YEAR FROM SYSDATE) THEN pes.id END) AS homicidios_ano
FROM bu.ocorrencia oc
LEFT JOIN bu.endereco ende ON ende.id = oc.endereco_id
LEFT JOIN bu.ocorrenciapessoa ope ON oc.id = ope.ocorrencia_id
LEFT JOIN bu.pessoa pes ON pes.id = ope.pessoa_id
LEFT JOIN bu.ocorrencia_pessoa_natur opn ON opn.ocorrenciapessoa_id = ope.id
LEFT JOIN bu.natureza nat_pes ON nat_pes.id = opn.natureza_id
INNER JOIN user_transacional.e_natureza_spi_tipificada_mview nat_tip_pes ON nat_tip_pes.spi_natureza_id = nat_pes.naturezaid
LEFT JOIN bu.ocorrencia_pessoa_natur_qual opnq ON opnq.ocorrenciapessoanatureza_id = opn.id
LEFT JOIN bu.qualificacao qua ON qua.id = opnq.qualificacoes_id
INNER JOIN spi.qalificacao qa ON qa.codigo_qualificacao = qua.qualificacaoid
INNER JOIN spi.qualificacao_categorias qcap ON qcap.qualificacao_categoria = qa.qualificacao_categoria
WHERE ende.estado_sigla = 'GO'
  AND EXTRACT(YEAR FROM oc.datafato) > '2015'
  AND oc.statusocorrencia = 'OCORRENCIA'
  AND (UPPER(nat_tip_pes.GRUPO) = 'HOMICÍDIO' OR nat_pes.naturezaid IN ('500001', '500002', '500003', '500004', '500005', '500006', '500007', '500011', '400711', '400712', '400001', '400002', '501199', '501200', '501201', '501202', '501203', '501204', '501220', '501136', '501137', '501138', '501139', '501140', '501141', '501288', '520269', '520323', '521062', '522242', '522243', '522262', '523006', '523007', '523008', '523009', '523010', '523011', '522745'))
  AND nat_pes.consumacaoenum = 'CONSUMADO'
  AND ope.tipopessoaenum = 'FISICA'
  AND qcap.nome = 'VÍTIMA'
'''

# Query principal de feminicídio
query_feminicidio = '''
SELECT
  COUNT(DISTINCT CASE WHEN TRUNC(oc.datafato) = TRUNC(SYSDATE) THEN pes.id END) AS feminicidios_hoje,
  COUNT(DISTINCT CASE WHEN TRUNC(oc.datafato) = TRUNC(SYSDATE-1) THEN pes.id END) AS feminicidios_ontem,
  COUNT(DISTINCT CASE WHEN EXTRACT(MONTH FROM oc.datafato) = EXTRACT(MONTH FROM SYSDATE) AND EXTRACT(YEAR FROM oc.datafato) = EXTRACT(YEAR FROM SYSDATE) THEN pes.id END) AS feminicidios_mes,
  COUNT(DISTINCT CASE WHEN EXTRACT(YEAR FROM oc.datafato) = EXTRACT(YEAR FROM SYSDATE) THEN pes.id END) AS feminicidios_ano
FROM bu.ocorrencia oc
LEFT JOIN bu.endereco ende ON ende.id = oc.endereco_id
LEFT JOIN bu.ocorrenciapessoa ope ON oc.id = ope.ocorrencia_id
LEFT JOIN bu.pessoa pes ON pes.id = ope.pessoa_id
LEFT JOIN bu.ocorrencia_pessoa_natur opn ON opn.ocorrenciapessoa_id = ope.id
LEFT JOIN bu.natureza nat_pes ON nat_pes.id = opn.natureza_id
INNER JOIN user_transacional.e_natureza_spi_tipificada_mview nat_tip_pes ON nat_tip_pes.spi_natureza_id = nat_pes.naturezaid
LEFT JOIN bu.ocorrencia_pessoa_natur_qual opnq ON opnq.ocorrenciapessoanatureza_id = opn.id
LEFT JOIN bu.qualificacao qua ON qua.id = opnq.qualificacoes_id
INNER JOIN spi.qalificacao qa ON qa.codigo_qualificacao = qua.qualificacaoid
INNER JOIN spi.qualificacao_categorias qcap ON qcap.qualificacao_categoria = qa.qualificacao_categoria
WHERE ende.estado_sigla = 'GO'
  AND EXTRACT(YEAR FROM oc.datafato) > '2015'
  AND oc.statusocorrencia = 'OCORRENCIA'
  AND (UPPER(nat_tip_pes.GRUPO) = 'FEMINICÍDIO' OR nat_pes.naturezaid IN ('501138', '501139', '501199', '501201', '501204', '520269', '520323','523011','523006'))
  AND nat_pes.consumacaoenum = 'CONSUMADO'
  AND ope.tipopessoaenum = 'FISICA'
  AND qcap.nome = 'VÍTIMA'
'''

# Query de homicídio por município (tabela)
query_municipio = '''
SELECT
  NVL(cid.nome, 'NÃO INFORMADO') AS municipio_nome,
  oc.id AS id_rai,
  TO_CHAR(TRUNC(oc.datafato), 'DD/MM/YYYY') AS datafato,
  COUNT(DISTINCT pes.id) AS total,
  CASE
    WHEN pes.sexo_nome = 'FEMININO' THEN 'F'
    WHEN pes.sexo_nome = 'MASCULINO' THEN 'M'
    ELSE 'NF'
  END AS sexo
FROM bu.ocorrencia oc
LEFT JOIN bu.endereco ende
     INNER JOIN sspj.bairros bai
           LEFT JOIN (SELECT cod_bairro, LISTAGG(eor.sigla, ', ') AS siglas FROM sicad.circunscricao circ INNER JOIN sicad.estrutura_organizacional_real eor ON eor.cod_estrutura_organizacional = circ.cod_estrutura_organizacional GROUP BY cod_bairro) area
           ON area.cod_bairro = bai.bairro
           LEFT JOIN sspj.aisps ais
                LEFT JOIN sspj.risps ris
                ON ris.risp = ais.risp
           ON ais.aisp = bai.aisp
           LEFT JOIN sspj.cidades cid
                LEFT JOIN sspj.cidades_ibge cib
                ON cib.codigo_sspj = cid.cidade
                LEFT JOIN sspj.microrregioes mic
                      LEFT JOIN sspj.mesorregioes mes
                      ON mes.mesorregiao = mic.mesorregiao
                ON mic.microrregiao = cid.microrregiao
           ON cid.cidade = bai.cidade
     ON bai.bairro = ende.bairro_id
ON ende.id = oc.endereco_id
LEFT JOIN bu.ocorrenciapessoa ope 
     LEFT JOIN bu.pessoa pes 
     ON pes.id = ope.pessoa_id
     LEFT JOIN bu.ocorrencia_pessoa_natur opn
          LEFT JOIN bu.natureza nat_pes
               INNER JOIN user_transacional.e_natureza_spi_tipificada_mview nat_tip_pes
               ON nat_tip_pes.spi_natureza_id = nat_pes.naturezaid
          ON nat_pes.id = opn.natureza_id  
          LEFT JOIN bu.ocorrencia_pessoa_natur_qual opnq
               LEFT JOIN bu.qualificacao qua
                     INNER JOIN spi.qalificacao qa
                           INNER JOIN spi.qualificacao_categorias qcap
                           ON qcap.qualificacao_categoria = qa.qualificacao_categoria
                     ON qa.codigo_qualificacao = qua.qualificacaoid
               ON qua.id = opnq.qualificacoes_id
          ON opnq.ocorrenciapessoanatureza_id = opn.id 
     ON opn.ocorrenciapessoa_id = ope.id
ON oc.id = ope.ocorrencia_id 
WHERE
ende.estado_sigla = 'GO'
AND TRUNC(oc.datafato) = TRUNC(SYSDATE - 1)
AND oc.statusocorrencia = 'OCORRENCIA'
AND (UPPER(nat_tip_pes.GRUPO) = 'HOMICÍDIO' OR nat_pes.naturezaid IN ('500001', '500002', '500003', '500004', '500005', '500006', '500007', '500011', '400711', '400712', '400001', '400002', '501199', '501200', '501201', '501202', '501203', '501204', '501220', '501136', '501137', '501138', '501139', '501140', '501141', '501288', '520269', '520323', '521062', '522242', '522243', '522262', '523006', '523007', '523008', '523009', '523010', '523011', '522745'))
AND nat_pes.consumacaoenum = 'CONSUMADO'
AND ope.tipopessoaenum = 'FISICA' 
AND qcap.nome = 'VÍTIMA'
GROUP BY
  cid.nome, oc.id,oc.datafato, 
  CASE
    WHEN pes.sexo_nome = 'FEMININO' THEN 'F'
    WHEN pes.sexo_nome = 'MASCULINO' THEN 'M'
    ELSE 'NF'
  END
ORDER BY municipio_nome, id_rai,oc.datafato
'''

# Query de homicídio comparativo dois anos (gráfico)
query_homicidio_comparativo_dois_anos = '''
SELECT DISTINCT
  *
FROM (
SELECT
  pes.id AS pessoa_id,
  EXTRACT(MONTH FROM oc.datafato) AS mes_fato,
  EXTRACT(YEAR FROM oc.datafato) AS ano_fato
FROM bu.ocorrencia oc
LEFT JOIN bu.endereco ende ON ende.id = oc.endereco_id
LEFT JOIN bu.ocorrenciapessoa ope 
     LEFT JOIN bu.pessoa pes 
  ON pes.id = ope.pessoa_id
  LEFT JOIN bu.ocorrencia_pessoa_natur opn
     LEFT JOIN bu.natureza nat_pes
         INNER JOIN user_transacional.e_natureza_spi_tipificada_mview nat_tip_pes
               ON nat_tip_pes.spi_natureza_id = nat_pes.naturezaid
       ON nat_pes.id = opn.natureza_id  
    LEFT JOIN bu.ocorrencia_pessoa_natur_qual opnq
      LEFT JOIN bu.qualificacao qua
         INNER JOIN spi.qalificacao qa
            INNER JOIN spi.qualificacao_categorias qcap
            ON qcap.qualificacao_categoria = qa.qualificacao_categoria
         ON qa.codigo_qualificacao = qua.qualificacaoid
      ON qua.id = opnq.qualificacoes_id
    ON opnq.ocorrenciapessoanatureza_id = opn.id 
  ON opn.ocorrenciapessoa_id = ope.id
ON oc.id = ope.ocorrencia_id 
WHERE
ende.estado_sigla = 'GO'
AND (EXTRACT(YEAR FROM oc.datafato) = EXTRACT(YEAR FROM ADD_MONTHS(SYSDATE, -12)) OR (EXTRACT(YEAR FROM oc.datafato) = EXTRACT(YEAR FROM SYSDATE)AND TRUNC(oc.datafato) <= TRUNC(SYSDATE - 1)))
AND oc.statusocorrencia = 'OCORRENCIA'
AND (UPPER(nat_tip_pes.GRUPO) = 'HOMICÍDIO' OR nat_pes.naturezaid IN ('500001', '500002', '500003', '500004', '500005', '500006', '500007', '500011', '400711', '400712', '400001', '400002', '501199', '501200', '501201', '501202', '501203', '501204', '501220', '501136', '501137', '501138', '501139', '501140', '501141', '501288', '520269', '520323', '521062', '522242', '522243', '522262', '523006', '523007', '523008', '523009', '523010', '523011', '522745'))
AND nat_pes.consumacaoenum = 'CONSUMADO'
AND ope.tipopessoaenum = 'FISICA' 
AND qcap.nome = 'VÍTIMA'
) PIVOT (
  COUNT(pessoa_id)
  FOR mes_fato IN (01 AS "JAN", 02 AS "FEV", 03 AS "MAR", 04 AS "ABR", 05 AS "MAI", 06 AS "JUN", 07 AS "JUL", 08 AS "AGO", 09 AS "SET", 10 AS "OUT", 11 AS "NOV", 12 AS "DEZ")
)
ORDER BY
  ano_fato 
'''

queries = [
    ("Homicídio", query_homicidio),
    ("Feminicídio", query_feminicidio),
    ("Município", query_municipio),
    ("Homicídio Ultimos 2 Anos", query_homicidio_comparativo_dois_anos)
]
resultados = {}
tempos_execucao = {}

for nome, query in tqdm(queries, desc="Executando consultas"):
    start = time.time()
    cursor.execute(query)
    if nome in ["Município", "Homicídio Ultimos 2 Anos"]:
        columns = [str(col[0]) for col in cursor.description]
        rows = [list(row) for row in cursor.fetchall()]
        resultados[nome] = (columns, rows)
    else:
        resultados[nome] = cursor.fetchone()
    end = time.time()
    tempos_execucao[nome] = end - start
    print(f"Tempo de execução da consulta {nome}: {tempos_execucao[nome]:.2f} segundos")

# Extrai os resultados
homicidios_hoje, homicidios_ontem, homicidios_mes, homicidios_ano = resultados["Homicídio"]
feminicidios_hoje, feminicidios_ontem, feminicidios_mes, feminicidios_ano = resultados["Feminicídio"]

from datetime import datetime, timedelta
hoje = datetime.now()
ontem = hoje - timedelta(days=1)
mes_atual = hoje.strftime('%b/%Y')

# --- INÍCIO DA GERAÇÃO DO PDF ---
pdf = PDFComRodape()
pdf.add_page()

# --- CABEÇALHO DO PDF (LOGO E TÍTULO INSTITUCIONAL) ---
pdf.image('img/LogoRelatorio.jpg', x=10, y=8, w=190)
pdf.ln(25)

# --- CONTEXTO: CAIXA DE TEXTO COM INDICADORES ---
# --- Desenha a caixa para o texto ---
caixa_x = 10
caixa_y = pdf.get_y() + 5
caixa_w = 110
caixa_h = 50  # altura estimada, pode ser ajustada

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

# Linha 1
escreve_linha_valor(f'Homicídios em {ontem.strftime("%d/%m/%Y")}', homicidios_ontem)
linha_y += linha_h
# Linha 2
escreve_linha_valor(f'Homicídios no mês {mes_atual}', homicidios_mes)
linha_y += linha_h
# Linha 3
escreve_linha_valor(f'Homicídios no ano {hoje.year}', homicidios_ano)
linha_y += linha_h
# Linha 4
escreve_linha_valor(f'Feminicídios no mês {mes_atual}', feminicidios_mes)
linha_y += linha_h
# Linha 5
escreve_linha_valor(f'Feminicídios no ano {hoje.year}', feminicidios_ano)
linha_y += linha_h

# Observação
pdf.set_xy(caixa_x + margem, linha_y)
pdf.set_font('Arial', 'I', 9)
pdf.cell(0, linha_h, 'Obs.: No número de Homicídios estão contabilizados os Feminicídios.', ln=1)

# --- KPIs À DIREITA ---
kpi_x = caixa_x + caixa_w + 10
kpi_y = caixa_y  # alinhado com a caixa
pdf.set_xy(kpi_x, kpi_y)
pdf.set_font('Arial', '', 12)
pdf.set_text_color(100, 100, 100)
pdf.cell(0, 8, f'Homicídios em: {hoje.strftime("%d/%m/%Y")}', ln=1)

pdf.set_font('Arial', 'B', 28)
pdf.set_text_color(30, 80, 160)
pdf.set_x(kpi_x)
pdf.cell(0, 15, str(homicidios_hoje), ln=1, align='C')

pdf.set_font('Arial', '', 12)
pdf.set_text_color(100, 100, 100)
pdf.set_x(kpi_x)
pdf.cell(0, 8, f'Homicídios em mês: {mes_atual}', ln=1)

pdf.set_font('Arial', 'B', 28)
pdf.set_text_color(30, 80, 160)
pdf.set_x(kpi_x)
pdf.cell(0, 15, str(homicidios_mes), ln=1, align='C')

# --- TABELA DE HOMICÍDIOS POR MUNICÍPIO ---
columns, rows = resultados["Município"]

# Espaço antes da tabela
pdf.ln(5)

# Definir ontem_data antes do uso
from datetime import timedelta
ontem_data = (hoje - timedelta(days=1)).strftime('%d/%m/%Y')

# Título da tabela
pdf.set_font('Arial', 'B', 12)
pdf.set_text_color(0, 0, 0)  # Preto
titulo = f'Homicídios - Dia Anterior por Município : {ontem_data}'
pdf.cell(0, 10, titulo, ln=1, align='L')

# Cabeçalho da tabela
col_widths = [70, 35, 30, 25, 30]  # Ajuste para totalizar ~190 (A4)
pdf.set_font('Arial', 'B', 10)
pdf.set_fill_color(230, 230, 230)
pdf.set_draw_color(0, 0, 0)  # Preto para borda
pdf.set_text_color(0, 0, 0)  # Preto para texto
for i, col in enumerate(columns):
    pdf.cell(col_widths[i], 8, str(col).upper(), 1, 0, 'C', fill=True)
pdf.ln()

# Dados
pdf.set_font('Arial', '', 10)
pdf.set_text_color(0, 0, 0)  # Preto para texto
def safe_str(item):
    return str(item) if item is not None else ''
for row in rows:
    for i, item in enumerate(row):
        pdf.cell(col_widths[i], 8, safe_str(item), 1, 0, 'C')
    pdf.ln()

# --- GRAFICO DE HOMICÍDIOS UTIMOS 2 ANOS ---
# Pegue os dados do resultado da query
columns_graf, rows_graf = resultados["Homicídio Ultimos 2 Anos"]

# Crie o DataFrame
df_graf = pd.DataFrame(rows_graf, columns=columns_graf)
from datetime import datetime
mes_corrente = datetime.now().month
meses = ['JAN','FEV','MAR','ABR','MAI','JUN','JUL','AGO','SET','OUT','NOV','DEZ']

plt.figure(figsize=(10, 3.0))
for _, row in df_graf.iterrows():
    ano = int(row['ANO_FATO'])
    if ano == datetime.now().year:
        meses_plot = meses[:mes_corrente]
        valores = [int(row[m]) if row[m] is not None else 0 for m in meses_plot]
    else:
        meses_plot = meses
        valores = [int(row[m]) if row[m] is not None else 0 for m in meses_plot]
    sns.lineplot(x=meses_plot, y=valores, marker='o', label=ano)
    for i, v in enumerate(valores):
        if v > 0:
            plt.text(i, v, str(v), ha='center', va='bottom', fontsize=8, bbox=dict(facecolor='white', alpha=0.8, edgecolor='none'))
plt.legend(title='ANO', bbox_to_anchor=(1.00, 1), loc='upper left', fontsize=8, title_fontsize=9)
# plt.title('Homicídios - Comparativo ano atual com os últimos dois anos', loc='left',fontsize=12,fontweight='bold',fontname='Arial')
plt.ylabel('Homicídios')
plt.yticks([])
plt.xlabel('')
plt.tight_layout()
plt.savefig('grafico_homicidios.png', dpi=150, bbox_inches='tight')
plt.close()
# Após a tabela:
pdf.ln(3)  # Espaço maior entre a tabela e o título do gráfico
pdf.set_font('Arial', 'B', 12)
pdf.set_text_color(0, 0, 0)
pdf.cell(0, 10, 'Homicídios - Comparativo ano atual com os últimos dois anos', ln=1, align='L')
#pdf.ln()  # Espaço pequeno entre o título e o gráfico
pdf.image('grafico_homicidios.png', x=5, w=200)
pdf.set_font('Arial', 'I', 9)
pdf.cell(0, 8, f'Até {ontem_data}', ln=1, align='L')

# --- ATRIBUIÇÃO DOS TEMPOS DE EXECUÇÃO PARA O RODAPÉ ---
# --- Antes de salvar, defina os tempos: ---
pdf.tempo_homicidio = f'{tempos_execucao["Homicídio"]:.2f}'
pdf.tempo_feminicidio = f'{tempos_execucao["Feminicídio"]:.2f}'
pdf.tempo_municipio = f'{tempos_execucao["Município"]:.2f}'
pdf.tempo_homicidio_comparativo_dois_anos = f'{tempos_execucao["Homicídio Ultimos 2 Anos"]:.2f}'

# --- SALVANDO O PDF ---
# --- Antes de salvar, defina os tempos: ---
pdf.output('task/relatorio_homicidios.pdf')

cursor.close()
conn.close()