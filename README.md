# WebScrepStatusQlik
Sistema automatizado de monitoramento e relatórios para Qlik Sense com integração WhatsApp via Evolution API.

## 📋 Visão Geral
O WebScrepStatusQlik é uma solução completa de automação que monitora tarefas do Qlik Sense (QMC, NPrinting, Desktop, ETL), gera relatórios PySQL e envia notificações via WhatsApp. O sistema utiliza web scraping com Selenium, processamento de dados com Python e integração com Evolution API para comunicação.

## 🏗️ Arquitetura do Sistema

### Módulos Principais

#### 1. **Crawler Qlik** (`crawler_qlik/`)
- **`status_qlik_task.py`**: Monitoramento principal de tarefas QMC (QAP e HUB)
- **`status_qlik_desktop.py`**: Monitoramento do Qlik Sense Desktop
- **`status_qlik_etl.py`**: Monitoramento de processos ETL
- **`network_config.py`**: Configurações de rede e conectividade

#### 2. **PySQL Reports** (`pysql/`)
- **`pysql_homicidios.py`**: Geração de relatórios de homicídios
- **`pysql_feminicidio.py`**: Geração de relatórios de feminicídio
- **`img_reports/`**: Imagens e gráficos dos relatórios
- **`reports_pysql/`**: Arquivos JSON com tempos de execução

#### 3. **Evolution API** (`evolution_api/`)
- **`send_qlik_evolution.py`**: Envio de relatórios Qlik via WhatsApp
- **`send_pysql_evolution.py`**: Envio de relatórios PySQL via WhatsApp
- **`docker-compose.yaml`**: Configuração Docker para Evolution API

#### 4. **Scheduler Centralizado**
- **`scheduler.py`**: Agendador principal com retry e logging
- **`scheduler_config.py`**: Configurações de horários e tarefas

## ⚙️ Configuração Inicial

### 1. Pré-requisitos
```bash
# Sistema
- Python 3.10+
- Google Chrome
- ChromeDriver compatível
- Git

# Windows (Build Tools)
- Visual Studio Build Tools com C++ build tools
- Windows 10/11 SDK
```

### 2. Instalação
```bash
# Clone o repositório
git clone https://github.com/wagnerhelio/WebScrepStatusQlik.git
cd WebScrepStatusQlik

# Crie ambiente virtual
python -m venv venv

# Ative o ambiente (Windows)
venv\Scripts\activate

# Instale dependências
pip install -r requirements.txt
```

### 3. Configuração de Variáveis de Ambiente
Copie `.env_exemple` para `.env` e configure:

```bash
# Credenciais Qlik
QLIK_USUARIO=dominio\\usuario
QLIK_EMAIL=bi@sspj.go.gov.br
QLIK_SENHA=suasenha123

# URLs Qlik QAP
QLIK_QMC_QAP=https://URLQLIK/qmc
QLIK_TASK_QAP=https://URLQLIK/qmc/tasks

# URLs Qlik HUB
QLIK_QMC_HUB=https://URLQLIK/qmc
QLIK_TASK_HUB=https://URLQLIK/qmc/tasks

# URLs NPrinting
QLIK_NPRINT=https://NPRINT
QLIK_NPRINT_TASK=https://NPRINT/#/tasks/executions

# ChromeDriver
CHROMEDRIVER=C:\caminho\para\chromedriver.exe

# Evolution API
EVOLUTION_BASE_URL=http://localhost:8080
EVOLUTION_API_TOKEN=seu_token
EVOLUTION_INSTANCE_ID=seu_instance_id
EVOLUTION_INSTANCE_NAME=nome_instancia
EVO_DESTINO=556290000000
EVO_DESTINO_GRUPO=NUMERO_GRUPO@g.us

# Banco Oracle (para relatórios PySQL)
ORACLE_HOST=IP_HOST
ORACLE_PORT=1521
ORACLE_TNS=NOME_TNS
ORACLE_USER=USUARIO
ORACLE_PASSWORD=SENHA
```

### 4. Configuração Evolution API
```bash
# Instale via Docker
cd evolution_api
docker-compose up -d

# Configure a instância no painel web
# Obtenha API_TOKEN, INSTANCE_ID e INSTANCE_NAME
```

## 🚀 Execução do Sistema

### Execução Automática (Recomendada)
```bash
# Execute o scheduler principal
python scheduler.py
```

O scheduler executa automaticamente:
- **A cada hora**: Monitoramento de status Qlik
- **05:00**: Geração de relatórios PySQL
- **06:00**: Monitoramento Qlik Desktop
- **07:00**: Monitoramento ETLs
- **08:00**: Envio relatórios Qlik via WhatsApp
- **08:05**: Envio relatórios PySQL via WhatsApp

### Execução Manual
```bash
# Monitoramento Qlik
python -m crawler_qlik.status_qlik_task
python -m crawler_qlik.status_qlik_desktop
python -m crawler_qlik.status_qlik_etl

# Relatórios PySQL
python -m pysql.pysql_homicidios
python -m pysql.pysql_feminicidio

# Envio via WhatsApp
python -m evolution_api.send_qlik_evolution
python -m evolution_api.send_pysql_evolution
```

## 📊 Funcionalidades Detalhadas

### 1. Monitoramento Qlik Sense

#### QMC (QAP e HUB)
- **Coleta de Status**: Verifica status de todas as tarefas agendadas
- **Download de Logs**: Baixa logs de erro automaticamente
- **Reinicialização**: Reinicia tarefas com falha
- **Relatórios**: Gera PDFs com estatísticas e painéis

#### NPrinting
- **Monitoramento de Execuções**: Acompanha execução de relatórios
- **Logs de Erro**: Coleta logs de falhas
- **Relatórios HTML**: Gera relatórios formatados

#### Desktop
- **Status de Aplicações**: Monitora aplicações Qlik Sense Desktop
- **Verificação de Conectividade**: Testa acesso aos servidores

#### ETL
- **Monitoramento de Processos**: Acompanha execução de ETLs
- **Verificação de Dependências**: Checa integridade dos dados

### 2. Relatórios PySQL

#### Homicídios
- **Análise Temporal**: Relatórios por dia, semana, mês e ano
- **Análise Regional**: Dados por região geográfica
- **Gráficos Automáticos**: Geração de visualizações
- **Exportação**: PDFs e imagens para distribuição

#### Feminicídios
- **Dados Especializados**: Análise específica de feminicídios
- **Indicadores**: Métricas e KPIs relevantes
- **Comparativos**: Análises temporais e regionais

### 3. Integração WhatsApp

#### Evolution API
- **Envio Individual**: Para números específicos
- **Envio em Grupo**: Para grupos configurados
- **Múltiplos Destinos**: Suporte a vários destinatários
- **Arquivos**: Envio de PDFs, imagens e relatórios

#### Tipos de Mensagem
- **Resumos Diários**: Status consolidado das tarefas
- **Relatórios Completos**: PDFs detalhados
- **Logs de Erro**: Arquivos de log para análise
- **Alertas**: Notificações de falhas críticas

## 📁 Estrutura de Arquivos

```
WebScrepStatusQlik/
├── crawler_qlik/                 # Módulo de monitoramento Qlik
│   ├── status_qlik_task.py      # Monitoramento principal
│   ├── status_qlik_desktop.py   # Monitoramento Desktop
│   ├── status_qlik_etl.py       # Monitoramento ETL
│   ├── network_config.py        # Configurações de rede
│   ├── chromedriver/            # WebDriver do Chrome
│   ├── errorlogs/               # Logs de erro coletados
│   ├── reports_qlik/            # Relatórios gerados
│   └── teamplate/               # Templates HTML
├── pysql/                       # Módulo de relatórios PySQL
│   ├── pysql_homicidios.py      # Relatórios de homicídios
│   ├── pysql_feminicidio.py     # Relatórios de feminicídio
│   ├── img_reports/             # Imagens dos relatórios
│   ├── reports_pysql/           # Dados de execução
│   └── errorlogs/               # Logs de erro PySQL
├── evolution_api/               # Módulo de integração WhatsApp
│   ├── send_qlik_evolution.py   # Envio relatórios Qlik
│   ├── send_pysql_evolution.py  # Envio relatórios PySQL
│   ├── docker-compose.yaml      # Configuração Docker
│   └── env.docker               # Variáveis Docker
├── technical_documentation/     # Documentação técnica
├── scheduler.py                 # Agendador principal
├── scheduler_config.py          # Configurações do scheduler
├── requirements.txt             # Dependências Python
├── .env_exemple                 # Exemplo de configuração
└── README.md                    # Este arquivo
```

## ⏰ Cronograma de Execução

| Horário | Tarefa | Descrição |
|---------|--------|-----------|
| **XX:00** | Status Qlik | Monitoramento a cada hora |
| **05:00** | Relatórios PySQL | Geração de relatórios |
| **06:00** | Status Desktop | Monitoramento Desktop |
| **07:00** | Status ETL | Monitoramento ETLs |
| **08:00** | Envio Qlik | Envio relatórios Qlik |
| **08:05** | Envio PySQL | Envio relatórios PySQL |

## 🔧 Configuração Avançada

### Personalização de Horários
Edite `scheduler_config.py` para modificar horários:

```python
TASKS_CONFIG = {
    "status_qlik": TaskConfig(
        name="Status Qlik",
        script_path="crawler_qlik.status_qlik_task",
        schedule_time=":00",  # A cada hora
        timeout=600,
        retry_count=3
    ),
    # Adicione ou modifique outras tarefas
}
```

### Configuração de Logs
```python
LOGGING_CONFIG = {
    "log_dir": "logs",
    "log_level": "INFO",
    "log_format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
}
```

### Timeouts e Retry
```python
EXECUTION_CONFIG = {
    "default_timeout": 300,
    "max_retry_count": 3,
    "retry_delay": 60
}
```

## 🐛 Troubleshooting

### Problemas Comuns

#### ChromeDriver
```bash
# Verifique a versão do Chrome
chrome://version/

# Baixe ChromeDriver compatível
https://chromedriver.chromium.org/downloads
```

#### Evolution API
```bash
# Verifique se a API está rodando
curl http://localhost:8080/instance/connectionState

# Teste a conexão
curl -X POST http://localhost:8080/message/sendText/INSTANCE_ID
```

#### Banco Oracle
```bash
# Teste a conexão
python -c "import cx_Oracle; print('Conexão OK')"
```

### Logs e Debug
```bash
# Logs do scheduler
tail -f logs/scheduler_YYYYMMDD.log

# Logs de erro
ls crawler_qlik/errorlogs/
ls pysql/errorlogs/
```

## 📈 Monitoramento e Manutenção

### Verificação de Status
```bash
# Status do scheduler
ps aux | grep scheduler.py

# Verificar execuções recentes
ls -la logs/

# Verificar arquivos gerados
ls -la crawler_qlik/reports_qlik/
ls -la pysql/reports_pysql/
```

### Limpeza Automática
O sistema limpa automaticamente:
- Logs antigos (configurável)
- Arquivos temporários
- Cache de relatórios

### Backup
```bash
# Backup dos relatórios
tar -czf backup_$(date +%Y%m%d).tar.gz \
    crawler_qlik/reports_qlik/ \
    pysql/reports_pysql/ \
    logs/
```

## 🤝 Contribuição

### Como Contribuir
1. Fork o projeto
2. Crie uma branch para sua feature
3. Commit suas mudanças
4. Push para a branch
5. Abra um Pull Request

### Padrões de Código
- Use Python 3.10+
- Siga PEP 8
- Documente funções e classes
- Adicione testes quando possível

## 📞 Suporte

### Equipe de Desenvolvimento
- **Wagner Filho**: wagner.helio@discente.ufg.br


### Recursos Adicionais
- [Documentação Técnica](technical_documentation/)
- [Exemplos de Configuração](technical_documentation/exemple/)
- [Diagramas do Sistema](technical_documentation/img/)

## 📄 Licença

Este projeto é licenciado sob a MIT License. Veja o arquivo [LICENSE](LICENSE) para detalhes.

---

**Desenvolvido com ❤️ pela equipe WebScrepStatusQlik**

