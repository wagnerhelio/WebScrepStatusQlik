import os
import oracledb as cx_Oracle
import time
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns
from fpdf import FPDF
from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv()

class PDFComRodape(FPDF):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tempo_homicidio = ""
        self.tempo_feminicidio = ""
        self.tempo_municipio = ""
        self.tempo_homicidio_comparativo_dois_anos = ""
        self.tempo_homicidio_comparativo_todos_anos = ""

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
        if self.tempo_homicidio_comparativo_todos_anos:
            self.cell(0, 8, f'Tempo de execução da consulta tempo_homicidio_comparativo_todos_anos: {self.tempo_homicidio_comparativo_todos_anos} segundos', ln=1, align='C')    

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
  AND EXTRACT(YEAR FROM oc.datafato) = EXTRACT(YEAR FROM SYSDATE)
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
  AND EXTRACT(YEAR FROM oc.datafato) = EXTRACT(YEAR FROM SYSDATE)
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
  COUNT(CASE WHEN pes.sexo_nome = 'FEMININO' THEN 1 END) AS F,
  COUNT(CASE WHEN pes.sexo_nome = 'MASCULINO' THEN 1 END) AS M,
  COUNT(CASE WHEN pes.sexo_nome IS NULL OR pes.sexo_nome NOT IN ('FEMININO', 'MASCULINO') THEN 1 END) AS NF
FROM bu.ocorrencia oc
LEFT JOIN bu.endereco ende
INNER JOIN sspj.bairros bai
      LEFT JOIN (
        SELECT cod_bairro, LISTAGG(eor.sigla, ', ') AS siglas
        FROM sicad.circunscricao circ
        INNER JOIN sicad.estrutura_organizacional_real eor
          ON eor.cod_estrutura_organizacional = circ.cod_estrutura_organizacional
        GROUP BY cod_bairro
      ) area ON area.cod_bairro = bai.bairro
      LEFT JOIN sspj.aisps ais
      LEFT JOIN sspj.risps ris ON ris.risp = ais.risp
ON ais.aisp = bai.aisp
LEFT JOIN sspj.cidades cid
     LEFT JOIN sspj.cidades_ibge cib ON cib.codigo_sspj = cid.cidade
          LEFT JOIN sspj.microrregioes mic
               LEFT JOIN sspj.mesorregioes mes ON mes.mesorregiao = mic.mesorregiao
          ON mic.microrregiao = cid.microrregiao
     ON cid.cidade = bai.cidade
ON bai.bairro = ende.bairro_id
ON ende.id = oc.endereco_id
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
  AND TRUNC(oc.datafato) = TRUNC(SYSDATE-1)
  AND oc.statusocorrencia = 'OCORRENCIA'
  AND (
    UPPER(nat_tip_pes.GRUPO) = 'HOMICÍDIO' OR nat_pes.naturezaid IN (
      '500001', '500002', '500003', '500004', '500005', '500006', '500007', '500011',
      '400711', '400712', '400001', '400002', '501199', '501200', '501201', '501202',
      '501203', '501204', '501220', '501136', '501137', '501138', '501139', '501140',
      '501141', '501288', '520269', '520323', '521062', '522242', '522243', '522262',
      '523006', '523007', '523008', '523009', '523010', '523011', '522745'
    )
  )
  AND nat_pes.consumacaoenum = 'CONSUMADO'
  AND ope.tipopessoaenum = 'FISICA'
  AND qcap.nome = 'VÍTIMA'
GROUP BY
  cid.nome, oc.id, oc.datafato
ORDER BY
  municipio_nome, id_rai, oc.datafato
'''

# Query de homicídio comparativo dois anos (gráfico)
query_homicidio_comparativo_dois_anos = '''
SELECT
  *
FROM (
SELECT DISTINCT
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
WHERE ende.estado_sigla = 'GO'
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

query_homicidio_comparativo_todos_anos ='''
SELECT 
  *
FROM (
SELECT DISTINCT
--  oc.id AS id_rai,
  pes.id AS pessoa_id,
  EXTRACT(MONTH FROM oc.datafato) AS mes_fato,
  EXTRACT(YEAR FROM oc.datafato) AS ano_fato
FROM bu.ocorrencia oc
--ENDERECO/AMBIENTE
LEFT JOIN bu.endereco ende
ON ende.id = oc.endereco_id
--PESSOA
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
AND TRUNC(oc.datafato) BETWEEN TO_DATE('01/01/2016', 'DD/MM/YYYY') AND TRUNC(SYSDATE - 1)
--AND oc.datafato >= TRUNC(SYSDATE - 1)
AND oc.statusocorrencia = 'OCORRENCIA'
--FILTRO
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

query_regioes_observatorio ='''
SELECT
CASE
    WHEN cid.uf <> 'GO' THEN NULL
    WHEN cid.cidade = 25300 THEN 'GOIÂNIA'
    WHEN cid.microrregiao = 520012 THEN 'ENTORNO DO DF'
    ELSE 'INTERIOR'
END AS regiao_observatorio,
COUNT(DISTINCT CASE WHEN oc.datafato >= TRUNC(ADD_MONTHS(SYSDATE, -12), 'MM') AND oc.datafato <  TRUNC(ADD_MONTHS(SYSDATE, -11), 'MM') THEN pes.id END) AS mes_anterior_fechado,
COUNT(DISTINCT CASE WHEN oc.datafato BETWEEN ADD_MONTHS(TRUNC(SYSDATE, 'MM'), -12) AND ADD_MONTHS(TRUNC(SYSDATE), -12) THEN pes.id END) AS periodo_ano_anterior,
COUNT(DISTINCT CASE WHEN oc.datafato BETWEEN TRUNC(SYSDATE, 'MM') AND TRUNC(SYSDATE)THEN pes.id END) AS periodo_ano_atual,
ROUND((COUNT(DISTINCT CASE WHEN oc.datafato BETWEEN TRUNC(SYSDATE, 'MM') AND TRUNC(SYSDATE) THEN pes.id END) - COUNT(DISTINCT CASE  WHEN oc.datafato BETWEEN ADD_MONTHS(TRUNC(SYSDATE, 'MM'), -12) AND ADD_MONTHS(TRUNC(SYSDATE), -12) THEN pes.id END)) * 100.0 / NULLIF(COUNT(DISTINCT CASE WHEN oc.datafato BETWEEN ADD_MONTHS(TRUNC(SYSDATE, 'MM'), -12) AND ADD_MONTHS(TRUNC(SYSDATE), -12) THEN pes.id END), 0), 2) AS variacao_percentual,
COUNT(DISTINCT CASE WHEN oc.datafato BETWEEN TRUNC(ADD_MONTHS(SYSDATE, -12), 'YYYY') AND ADD_MONTHS(TRUNC(SYSDATE), -12) THEN pes.id END) AS acumulado_ano_anterior,
COUNT(DISTINCT CASE WHEN oc.datafato BETWEEN TRUNC(SYSDATE, 'YYYY') AND TRUNC(SYSDATE) THEN pes.id END) AS acumulado_ano_atual,
ROUND(( COUNT(DISTINCT CASE WHEN oc.datafato BETWEEN TRUNC(SYSDATE, 'YYYY') AND TRUNC(SYSDATE) THEN pes.id END) - COUNT(DISTINCT CASE WHEN oc.datafato BETWEEN TRUNC(ADD_MONTHS(SYSDATE, -12), 'YYYY') AND ADD_MONTHS(TRUNC(SYSDATE), -12) THEN pes.id END)) * 100.0 / NULLIF(COUNT(DISTINCT CASE WHEN oc.datafato BETWEEN TRUNC(ADD_MONTHS(SYSDATE, -12), 'YYYY') AND ADD_MONTHS(TRUNC(SYSDATE), -12)THEN pes.id END), 0), 2) AS variacao_acumulado_percentual,
SUM(cib.populacao) AS populacao_total
FROM bu.ocorrencia oc
LEFT JOIN bu.endereco ende
INNER JOIN sspj.bairros bai
      LEFT JOIN (
        SELECT cod_bairro, LISTAGG(eor.sigla, ', ') AS siglas
        FROM sicad.circunscricao circ
        INNER JOIN sicad.estrutura_organizacional_real eor
          ON eor.cod_estrutura_organizacional = circ.cod_estrutura_organizacional
        GROUP BY cod_bairro
      ) area ON area.cod_bairro = bai.bairro
      LEFT JOIN sspj.aisps ais
      LEFT JOIN sspj.risps ris ON ris.risp = ais.risp
ON ais.aisp = bai.aisp
LEFT JOIN sspj.cidades cid
     LEFT JOIN sspj.cidades_ibge cib ON cib.codigo_sspj = cid.cidade
          LEFT JOIN sspj.microrregioes mic
               LEFT JOIN sspj.mesorregioes mes ON mes.mesorregiao = mic.mesorregiao
          ON mic.microrregiao = cid.microrregiao
     ON cid.cidade = bai.cidade
ON bai.bairro = ende.bairro_id
ON ende.id = oc.endereco_id
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
AND (EXTRACT(YEAR FROM oc.datafato) = EXTRACT(YEAR FROM ADD_MONTHS(SYSDATE, -12)) OR (EXTRACT(YEAR FROM oc.datafato) = EXTRACT(YEAR FROM SYSDATE)AND TRUNC(oc.datafato) <= TRUNC(SYSDATE - 1)))
AND oc.statusocorrencia = 'OCORRENCIA'
AND (
    UPPER(nat_tip_pes.GRUPO) = 'HOMICÍDIO' OR nat_pes.naturezaid IN (
      '500001', '500002', '500003', '500004', '500005', '500006', '500007', '500011',
      '400711', '400712', '400001', '400002', '501199', '501200', '501201', '501202',
      '501203', '501204', '501220', '501136', '501137', '501138', '501139', '501140',
      '501141', '501288', '520269', '520323', '521062', '522242', '522243', '522262',
      '523006', '523007', '523008', '523009', '523010', '523011', '522745'
    )
  )
AND nat_pes.consumacaoenum = 'CONSUMADO'
AND ope.tipopessoaenum = 'FISICA'
AND qcap.nome = 'VÍTIMA'
GROUP BY
CASE
	WHEN cid.uf <> 'GO' THEN NULL
	WHEN cid.cidade = 25300 THEN 'GOIÂNIA'
	WHEN cid.microrregiao = 520012 THEN 'ENTORNO DO DF'
ELSE 'INTERIOR'
END
'''

query_homicidios_comparativo_dia ='''
SELECT
  TO_CHAR(oc.datafato, 'DD') || '/' || INITCAP(TO_CHAR(oc.datafato, 'Mon', 'NLS_DATE_LANGUAGE=PORTUGUESE')) AS data,
  EXTRACT(YEAR FROM oc.datafato) AS ano,
  COUNT(DISTINCT pes.id) AS homicidios
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
  AND oc.statusocorrencia = 'OCORRENCIA'
  AND (UPPER(nat_tip_pes.GRUPO) = 'HOMICÍDIO' OR nat_pes.naturezaid IN ('500001', '500002', '500003', '500004', '500005', '500006', '500007', '500011', '400711', '400712', '400001', '400002', '501199', '501200', '501201', '501202', '501203', '501204', '501220', '501136', '501137', '501138', '501139', '501140', '501141', '501288', '520269', '520323', '521062', '522242', '522243', '522262', '523006', '523007', '523008', '523009', '523010', '523011', '522745'))
  AND nat_pes.consumacaoenum = 'CONSUMADO'
  AND ope.tipopessoaenum = 'FISICA'
  AND qcap.nome = 'VÍTIMA'
  AND EXTRACT(MONTH FROM oc.datafato) = EXTRACT(MONTH FROM SYSDATE)
  AND EXTRACT(DAY FROM oc.datafato) <= EXTRACT(DAY FROM SYSDATE - 1)
  AND EXTRACT(YEAR FROM oc.datafato) IN (EXTRACT(YEAR FROM SYSDATE),EXTRACT(YEAR FROM SYSDATE) - 1)
GROUP BY
  TO_CHAR(oc.datafato, 'DD'),
  TO_CHAR(oc.datafato, 'Mon', 'NLS_DATE_LANGUAGE=PORTUGUESE'),
  EXTRACT(YEAR FROM oc.datafato)
ORDER BY
  TO_NUMBER(TO_CHAR(oc.datafato, 'DD')), ano
'''

query_homicidios_comparativo_dia_observatorio ='''
SELECT
  CASE
	  WHEN cid.uf <> 'GO' THEN NULL
	  WHEN cid.cidade = 25300 THEN 'GOIÂNIA'
	  WHEN cid.microrregiao = 520012 THEN 'ENTORNO DO DF'
	  ELSE 'INTERIOR'
  END AS regiao_observatorio,
  TO_CHAR(oc.datafato, 'DD') || '/' || INITCAP(TO_CHAR(oc.datafato, 'Mon', 'NLS_DATE_LANGUAGE=PORTUGUESE')) AS data,
  EXTRACT(YEAR FROM oc.datafato) AS ano,
  COUNT(DISTINCT pes.id) AS homicidios
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
  AND oc.statusocorrencia = 'OCORRENCIA'
  AND (UPPER(nat_tip_pes.GRUPO) = 'HOMICÍDIO' OR nat_pes.naturezaid IN ('500001', '500002', '500003', '500004', '500005', '500006', '500007', '500011', '400711', '400712', '400001', '400002', '501199', '501200', '501201', '501202', '501203', '501204', '501220', '501136', '501137', '501138', '501139', '501140', '501141', '501288', '520269', '520323', '521062', '522242', '522243', '522262', '523006', '523007', '523008', '523009', '523010', '523011', '522745'))
  AND nat_pes.consumacaoenum = 'CONSUMADO'
  AND ope.tipopessoaenum = 'FISICA'
  AND qcap.nome = 'VÍTIMA'
  AND EXTRACT(MONTH FROM oc.datafato) = EXTRACT(MONTH FROM SYSDATE)
  AND EXTRACT(DAY FROM oc.datafato) <= EXTRACT(DAY FROM SYSDATE - 1)
  AND EXTRACT(YEAR FROM oc.datafato) = EXTRACT(YEAR FROM SYSDATE)
GROUP BY
  CASE
	  WHEN cid.uf <> 'GO' THEN NULL
	  WHEN cid.cidade = 25300 THEN 'GOIÂNIA'
	  WHEN cid.microrregiao = 520012 THEN 'ENTORNO DO DF'
	  ELSE 'INTERIOR'
  END,
  TO_CHAR(oc.datafato, 'DD'),
  TO_CHAR(oc.datafato, 'Mon', 'NLS_DATE_LANGUAGE=PORTUGUESE'),
  EXTRACT(YEAR FROM oc.datafato)
ORDER BY
  TO_NUMBER(TO_CHAR(oc.datafato, 'DD')), ano
'''

query_homicidios_comparativo_mes_observatorio ='''
SELECT
  CASE
	  WHEN cid.uf <> 'GO' THEN NULL
	  WHEN cid.cidade = 25300 THEN 'GOIÂNIA'
	  WHEN cid.microrregiao = 520012 THEN 'ENTORNO DO DF'
	  ELSE 'INTERIOR'
  END AS regiao_observatorio,
  INITCAP(TO_CHAR(oc.datafato, 'Mon', 'NLS_DATE_LANGUAGE=PORTUGUESE')) AS mes,
  EXTRACT(MONTH FROM oc.datafato) AS numero_mes,
  COUNT(DISTINCT pes.id) AS homicidios
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
  AND oc.statusocorrencia = 'OCORRENCIA'
  AND (UPPER(nat_tip_pes.GRUPO) = 'HOMICÍDIO' OR nat_pes.naturezaid IN ('500001', '500002', '500003', '500004', '500005', '500006', '500007', '500011', '400711', '400712', '400001', '400002', '501199', '501200', '501201', '501202', '501203', '501204', '501220', '501136', '501137', '501138', '501139', '501140', '501141', '501288', '520269', '520323', '521062', '522242', '522243', '522262', '523006', '523007', '523008', '523009', '523010', '523011', '522745'))
  AND nat_pes.consumacaoenum = 'CONSUMADO'
  AND ope.tipopessoaenum = 'FISICA'
  AND qcap.nome = 'VÍTIMA'
  AND EXTRACT(DAY FROM oc.datafato) <= EXTRACT(DAY FROM SYSDATE - 1)
  AND EXTRACT(YEAR FROM oc.datafato) = EXTRACT(YEAR FROM SYSDATE)
GROUP BY
  CASE
	  WHEN cid.uf <> 'GO' THEN NULL
	  WHEN cid.cidade = 25300 THEN 'GOIÂNIA'
	  WHEN cid.microrregiao = 520012 THEN 'ENTORNO DO DF'
	  ELSE 'INTERIOR'
  END,
  INITCAP(TO_CHAR(oc.datafato, 'Mon', 'NLS_DATE_LANGUAGE=PORTUGUESE')),
  EXTRACT(MONTH FROM oc.datafato)
ORDER BY
  EXTRACT(MONTH FROM oc.datafato) 
'''

queries = [
    ("Homicídio", query_homicidio),
    ("Feminicídio", query_feminicidio),
    ("Município", query_municipio),
    ("Homicídio Ultimos 2 Anos", query_homicidio_comparativo_dois_anos),
    ("Homicídio Todos os Anos", query_homicidio_comparativo_todos_anos),
    ("Regioes Observatório", query_regioes_observatorio),
    ("Homicídio Comparativo por Dia",query_homicidios_comparativo_dia),
    ("Homicídio Comparativo por Dia Observatório",query_homicidios_comparativo_dia_observatorio),
    ("Homicídio Comparativo por Mes Observatório",query_homicidios_comparativo_mes_observatorio)

]
resultados = {}
tempos_execucao = {}

for nome, query in tqdm(queries, desc="Executando consultas"):
    start = time.time()
    cursor.execute(query)
    if nome in ["Município", "Homicídio Ultimos 2 Anos","Homicídio Todos os Anos","Regioes Observatório","Homicídio Comparativo por Dia","Homicídio Comparativo por Dia Observatório","Homicídio Comparativo por Mes Observatório"]:
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
mes_atual = hoje.strftime('%b').capitalize()  # Ex: 'Jul'
ano_atual = hoje.year
dia_ontem = ontem.day
ano_anterior = ano_atual - 1

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
columns_municipio, rows_municipio = resultados["Município"]

# Espaço antes da tabela
pdf.ln(5)

# Definir ontem_data antes do uso
from datetime import timedelta
ontem_data = (hoje - timedelta(days=1)).strftime('%d/%m/%Y')

# Título da tabela
pdf.set_font('Arial', 'B', 12)
pdf.set_text_color(0, 0, 0)  # Preto
titulo_municipio = f'Homicídios - Dia Anterior por Município : {ontem_data}'
pdf.cell(0, 10, titulo_municipio, ln=1, align='L')

# Cabeçalho da tabela de município
col_widths_municipio = [38, 22, 22, 12, 12, 12, 12]  # 7 colunas: municipio_nome, id_rai, datafato, total, F, M, NF
pdf.set_font('Arial', 'B', 8)
pdf.set_fill_color(230, 230, 230)
pdf.set_draw_color(0, 0, 0)  # Preto para borda
pdf.set_text_color(0, 0, 0)  # Preto para texto
for i, col in enumerate(columns_municipio):
    pdf.cell(col_widths_municipio[i], 6, str(col).upper(), 1, 0, 'C', fill=True)
pdf.ln()

# Dados da tabela de município
pdf.set_font('Arial', '', 8)
pdf.set_text_color(0, 0, 0)  # Preto para texto
def safe_str(item):
    return str(item) if item is not None else ''
for row in rows_municipio:
    for i, item in enumerate(row):
        pdf.cell(col_widths_municipio[i], 6, safe_str(item), 1, 0, 'C')
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
pdf.set_text_color(0, 0, 0)  # Preto
titulo_comparativo_dois_anos = f'Homicídios - Comparativo ano atual com os últimos dois anos : {ontem_data}'
pdf.cell(0, 10, titulo_comparativo_dois_anos, ln=1, align='L')
#pdf.ln()  # Espaço pequeno entre o título e o gráfico
pdf.image('grafico_homicidios.png', x=5, w=200)
pdf.set_font('Arial', 'I', 9)
pdf.cell(0, 8, f'Até {ontem_data}', ln=1, align='L')

# --- TABELA DE HOMICÍDIOS POR MESES/ANOS (CONSULTA DE 13 COLUNAS) ---
columns_meses_anos, rows_meses_anos = resultados["Homicídio Todos os Anos"]

# Espaço antes da tabela
pdf.ln(4)

# Título da tabela
pdf.set_font('Arial', 'B', 12)
pdf.set_text_color(0, 0, 0)  # Preto
titulo_meses_anos = f'Tabela de Homicidios Comparativo por Ano até : {ontem_data}'
pdf.cell(0, 10, titulo_meses_anos, ln=1, align='L')

# Cabeçalho da tabela de meses/anos
# Para A4, largura útil ~190mm. Para 13 colunas, use ~14mm cada (ano pode ser 18mm, meses 14mm)
col_widths_meses_anos = [18] + [14]*12
pdf.set_font('Arial', 'B', 8)
pdf.set_fill_color(230, 230, 230)
pdf.set_draw_color(0, 0, 0)  # Preto para borda
pdf.set_text_color(0, 0, 0)  # Preto para texto
for i, col in enumerate(columns_meses_anos):
    pdf.cell(col_widths_meses_anos[i], 6, str(col).upper(), 1, 0, 'C', fill=True)
pdf.ln()

# Dados da tabela de meses/anos
pdf.set_font('Arial', '', 8)
pdf.set_text_color(0, 0, 0)  # Preto para texto
for row in rows_meses_anos:
    for i, item in enumerate(row):
        pdf.cell(col_widths_meses_anos[i], 6, safe_str(item), 1, 0, 'C')
    pdf.ln()

# --- TABELA DE REGIAO OBSERVATORIO ---
columns_regiao_observatorio_atualizada = [
    "REGIÃO",
    f"{mes_atual}/{ano_anterior} (fechado)",
    f"{mes_atual}/{ano_anterior} (até dia {dia_ontem})",
    f"{mes_atual}/{ano_atual} (até dia {dia_ontem})",
    "%",
    f"Acumulado Jan a {mes_atual} {ano_anterior} (até dia {dia_ontem})",
    f"Acumulado Jan a {mes_atual} {ano_atual} (até dia {dia_ontem})",
    "%",
    "Índice por 100K hab."
]

columns_regiao_observatorio, rows_regiao_observatorio = resultados["Regioes Observatório"]

# Espaço antes da tabela
pdf.ln(4)

# Título da tabela
pdf.set_font('Arial', 'B', 12)
pdf.set_text_color(0, 0, 0)  # Preto
titulo_regiao_observatorio = f'HOMICIDIOS POR REGIÕES - Comparativo Dia Anterior e Acumulado até : {ontem_data}'
pdf.cell(0, 10, titulo_regiao_observatorio, ln=1, align='L')

col_widths_regiao_observatorio = [25, 20, 20, 20, 15, 24, 24, 15, 25]  # 9 colunas
# Cabeçalho da tabela de regiões observatório (ajustado para quebra de linha, altura uniforme)
pdf.set_font('Arial', 'B', 8)
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
pdf.set_font('Arial', '', 8)
pdf.set_text_color(0, 0, 0)  # Preto para texto
for row in rows_regiao_observatorio:
    for i, item in enumerate(row):
        # Coloração e formatação para as colunas de %
        if i in [4, 7]:  # Índices das colunas de %
            valor = float(item) if item is not None else 0
            texto = f"{valor:.2f}%"
            if valor > 0:
                pdf.set_text_color(220, 20, 60)  # vermelho
            elif valor < 0:
                pdf.set_text_color(0, 128, 0)    # verde
            else:
                pdf.set_text_color(0, 0, 0)      # preto
            pdf.cell(col_widths_regiao_observatorio[i], 6, texto, 1, 0, 'C')
            pdf.set_text_color(0, 0, 0)  # reset
        else:
            pdf.cell(col_widths_regiao_observatorio[i], 6, safe_str(item), 1, 0, 'C')
    pdf.ln()

# --- GRAFICO COMPARATIVO POR DIA
columns_dia, rows_dia = resultados["Homicídio Comparativo por Dia"]
df_dia = pd.DataFrame(rows_dia, columns=columns_dia)

# Ajusta tipos e nomes
if not df_dia.empty:
    df_dia['ANO'] = df_dia['ANO'].astype(int)
    df_dia['HOMICIDIOS'] = df_dia['HOMICIDIOS'].astype(int)

    # Pivot para barras agrupadas
    df_pivot = df_dia.pivot(index='DATA', columns='ANO', values='HOMICIDIOS').fillna(0)
    df_pivot = df_pivot.reindex(sorted(df_pivot.index, key=lambda x: int(x.split('/')[0])))

    plt.figure(figsize=(10, 3.5))
    anos = sorted(df_pivot.columns)
    bar_width = 0.4
    x = range(len(df_pivot.index))
    cores = ['#3b3b98', '#218c5a']  # Azul e verde

    for i, ano in enumerate(anos):
        bars = plt.bar([xi + i*bar_width for xi in x], df_pivot[ano], width=bar_width, label=str(ano), color=cores[i % len(cores)])
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

    plt.xticks([xi + bar_width/2 for xi in x], list(df_pivot.index), rotation=45)
    plt.ylabel('Homicídios')
    #plt.title(f'Homicídios - Por Dia no mês atual: {hoje.strftime("%b/%Y")} : {ontem.strftime("%d/%m/%Y")}', loc='left', fontsize=12, fontweight='bold', fontname='Arial')
    plt.legend(title='', loc='best')
    plt.yticks([])
    plt.tight_layout()
    plt.savefig('grafico_homicidios_dia.png', dpi=150, bbox_inches='tight')
    plt.close()

    pdf.ln(3)
    pdf.set_font('Arial', 'B', 12)
    pdf.set_text_color(0, 0, 0)  # Preto
    titulo_mes_atual = f'Homicídios - Por Dia no mês atual: {hoje.strftime("%b/%Y")}'
    pdf.cell(0, 10, titulo_mes_atual, ln=1, align='L')
    pdf.image('grafico_homicidios_dia.png', x=5, w=200)
    pdf.set_font('Arial', 'I', 9)
    pdf.cell(0, 8, f'Até {ontem_data}', ln=1, align='L')

# --- TABELA COMPARATIVO POR DIA

# Título da tabela
pdf.set_font('Arial', 'B', 12)
pdf.set_text_color(0, 0, 0)  # Preto
titulo_por_dia = f'Homicídios Comparativo por Dia no Mês Atual : {ontem_data}'
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

# --- GRAFICO COMPARATIVO POR DIA OBSERVATÓRIO (por REGIAO_OBSERVATORIO)
columns_dia_obs, rows_dia_obs = resultados["Homicídio Comparativo por Dia Observatório"]
df_comparativo_dia = pd.DataFrame(rows_dia_obs, columns=columns_dia_obs)

if not df_comparativo_dia.empty:
    df_comparativo_dia['HOMICIDIOS'] = df_comparativo_dia['HOMICIDIOS'].astype(int)

    # Pivot por DATA e REGIAO_OBSERVATORIO
    df_pivot = df_comparativo_dia.pivot(index='DATA', columns='REGIAO_OBSERVATORIO', values='HOMICIDIOS').fillna(0)
    df_pivot = df_pivot.reindex(sorted(df_pivot.index, key=lambda x: int(x.split('/')[0])))

    plt.figure(figsize=(10, 3.5))
    regioes = sorted(df_pivot.columns)
    bar_width = 0.25
    x = range(len(df_pivot.index))
    cores = ['#e55039', '#3b3b98', '#f6b93b']  # Vermelho, Azul, Amarelo

    for i, regiao in enumerate(regioes):
        bars = plt.bar([xi + i * bar_width for xi in x], df_pivot[regiao], width=bar_width, label=regiao, color=cores[i % len(cores)])
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

    plt.xticks([xi + bar_width * (len(regioes)/2 - 0.5) for xi in x], list(df_pivot.index), rotation=45)
    plt.ylabel('Homicídios')
    plt.legend(title='', loc='best')
    plt.yticks([])
    plt.tight_layout()

    plt.savefig('grafico_homicidios_dia_regiao.png', dpi=150, bbox_inches='tight')
    plt.close()

    pdf.ln(3)
    pdf.set_font('Arial', 'B', 12)
    pdf.set_text_color(0, 0, 0)
    titulo_mes_regiao = f'Homicídios - Por Dia no mês atual: {hoje.strftime("%b/%Y")}'
    pdf.cell(0, 10, titulo_mes_regiao, ln=1, align='L')
    pdf.image('grafico_homicidios_dia_regiao.png', x=5, w=200)
    pdf.set_font('Arial', 'I', 9)
    pdf.cell(0, 8, f'Até {ontem_data}', ln=1, align='L')

# --- GRAFICO COMPARATIVO POR MES OBSERVATÓRIO (por REGIAO_OBSERVATORIO)

# --- TABELA COMPARATIVO POR MES OBSERVATÓRIO (por REGIAO_OBSERVATORIO)

# --- ATRIBUIÇÃO DOS TEMPOS DE EXECUÇÃO PARA O RODAPÉ ---
tempo_execucao_resumo = (
    f'Homicídio: {tempos_execucao["Homicídio"]:.2f} | '
    f'Feminicídio: {tempos_execucao["Feminicídio"]:.2f} | '
    f'Município: {tempos_execucao["Município"]:.2f} | '
    f'Homicídio 2 Anos: {tempos_execucao["Homicídio Ultimos 2 Anos"]:.2f} | '
    f'Homicídio Todos os Anos: {tempos_execucao["Homicídio Todos os Anos"]:.2f} | '
    f'Regiões Observatório: {tempos_execucao["Regioes Observatório"]:.2f} | '
    f'Homicídio Comparativo por Dia: {tempos_execucao["Homicídio Comparativo por Dia"]:.2f} '
    f'Homicídio Comparativo por Dia Observatório: {tempos_execucao["Homicídio Comparativo por Dia Observatório"]:.2f} '
    f'Homicídio Comparativo por Mes Observatório: {tempos_execucao["Homicídio Comparativo por Mes Observatório"]:.2f} '
)
pdf.set_font('Arial', '', 6)
pdf.cell(0, 8, tempo_execucao_resumo, ln=1, align='L')
# --- SALVANDO O PDF ---
# --- Antes de salvar, defina os tempos: ---
pdf.output('task/relatorio_homicidios.pdf')

cursor.close()
conn.close()