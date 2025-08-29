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

## 📁 Estrutura Detalhada do Projeto

### 📂 **Diretório Raiz**
```
WebScrepStatusQlik/
├── 📄 scheduler.py                    # Agendador principal do sistema
├── 📄 requirements.txt                # Dependências Python do projeto
├── 📄 .env_exemple                    # Exemplo de configuração de variáveis
├── 📄 LICENSE                         # Licença MIT do projeto
├── 📄 README.md                       # Documentação principal
├── 📄 .gitignore                      # Arquivos ignorados pelo Git
├── 📂 __pycache__/                    # Cache Python (gerado automaticamente)
└── 📂 .venv/                          # Ambiente virtual Python
```

### 📂 **crawler_qlik/** - Módulo de Monitoramento Qlik
```
crawler_qlik/
├── 📄 __init__.py                     # Inicializador do módulo Python
├── 📄 status_qlik_task.py             # Monitoramento principal de tarefas QMC (QAP e HUB)
├── 📄 status_qlik_desktop.py          # Monitoramento do Qlik Sense Desktop
├── 📄 status_qlik_etl.py              # Monitoramento de processos ETL
├── 📄 network_config.py               # Configurações de rede e conectividade
├── 📂 __pycache__/                    # Cache Python do módulo
├── 📂 chromedriver/                   # WebDriver do Chrome
│   ├── 📄 chromedriver.exe            # Executável do ChromeDriver para Windows
│   ├── 📄 chromedriver-win64.zip      # Arquivo compactado do ChromeDriver
│   ├── 📄 LICENSE.chromedriver        # Licença do ChromeDriver
│   └── 📄 THIRD_PARTY_NOTICES.chromedriver  # Notas de terceiros
├── 📂 errorlogs/                      # Logs de erro coletados pelo sistema
├── 📂 reports_qlik/                   # Relatórios gerados pelo monitoramento
└── 📂 teamplate/                      # Templates HTML para relatórios
    ├── 📄 template.html               # Template padrão para relatórios
    └── 📄 template_nprinting.html     # Template específico para NPrinting
```

### 📂 **pysql/** - Módulo de Relatórios PySQL
```
pysql/
├── 📄 pysql_homicidios.py             # Geração de relatórios de homicídios
├── 📄 pysql_feminicidio.py            # Geração de relatórios de feminicídio
├── 📂 img_reports/                    # Imagens e gráficos dos relatórios
│   └── 📄 LogoRelatorio.jpg           # Logo utilizado nos relatórios
├── 📂 reports_pysql/                  # Arquivos JSON com tempos de execução
│   ├── 📄 feminicidios_tempos_execucao.json  # Dados de tempo de execução feminicídios
│   └── 📄 homicidios_tempos_execucao.json    # Dados de tempo de execução homicídios
└── 📂 errorlogs/                      # Logs de erro dos scripts PySQL
```

### 📂 **evolution_api/** - Módulo de Integração WhatsApp
```
evolution_api/
├── 📄 send_qlik_evolution.py          # Envio de relatórios Qlik via WhatsApp
├── 📄 send_pysql_evolution.py         # Envio de relatórios PySQL via WhatsApp
├── 📄 docker-compose.yaml             # Configuração Docker para Evolution API
├── 📄 env.docker                      # Variáveis de ambiente para Docker
└── 📂 __pycache__/                    # Cache Python do módulo
```

### 📂 **technical_documentation/** - Documentação Técnica
```
technical_documentation/
├── 📄 relatorio_webscrepstatusqlik.tex  # Documentação em LaTeX
├── 📄 WebScrepStatusQlik__Monitoramento_Automatizado_de_Tarefas_do_Qlik_Sense_com_Envio_de_Alertas_via_WhatsApp.pdf  # Relatório técnico em PDF
├── 📂 exemple/                        # Exemplos de código e configuração
│   ├── 📄 relatorio_homicidios.py     # Exemplo de relatório de homicídios
│   ├── 📄 scheduler_statusqlik.py     # Exemplo de scheduler
│   ├── 📄 send_evolution.py           # Exemplo de envio via Evolution API
│   ├── 📄 send_statusqlik_evolution.py  # Exemplo de envio de status Qlik
│   ├── 📄 sendgroup_statusqlik_evolution.py  # Exemplo de envio para grupo
│   ├── 📄 sendnumber_statusqlik_evolution.py  # Exemplo de envio para número
│   ├── 📄 statusqlik_nprinting.py     # Exemplo de monitoramento NPrinting
│   ├── 📄 statusqlik_qmc.py           # Exemplo de monitoramento QMC
│   └── 📄 statusqliksensedesktop.py   # Exemplo de monitoramento Desktop
└── 📂 img/                            # Imagens e diagramas
    ├── 📄 Docker.png                  # Imagem relacionada ao Docker
    ├── 📄 WebScrep_QMC.drawio         # Diagrama do sistema em formato Draw.io
    ├── 📄 WebScrep_QMC.drawio.png     # Diagrama do sistema em PNG
    └── 📄 WebScrep_QMC.jpg            # Imagem do sistema QMC
```

## 📋 Descrição Detalhada dos Arquivos

### 🔧 **Arquivos de Configuração e Sistema**

#### **`scheduler.py`**
- **Função**: Agendador principal que coordena todas as tarefas do sistema
- **Recursos**: Execução programada, retry automático, logging detalhado
- **Horários**: Configuração flexível de execução das tarefas

#### **`requirements.txt`**
- **Função**: Lista todas as dependências Python necessárias
- **Inclui**: Selenium, pandas, matplotlib, cx_Oracle, python-dotenv, etc.

#### **`.env_exemple`**
- **Função**: Template com todas as variáveis de ambiente necessárias
- **Configurações**: Credenciais Qlik, URLs, Evolution API, banco Oracle

#### **`LICENSE`**
- **Função**: Licença MIT que permite uso, modificação e distribuição

### 🕷️ **Arquivos de Monitoramento Qlik**

#### **`crawler_qlik/status_qlik_task.py`**
- **Função**: Monitoramento principal de tarefas QMC (QAP e HUB)
- **Recursos**: Web scraping, coleta de status, download de logs, reinicialização automática
- **Saída**: Relatórios PDF e logs de erro

#### **`crawler_qlik/status_qlik_desktop.py`**
- **Função**: Monitoramento específico do Qlik Sense Desktop
- **Recursos**: Verificação de aplicações, conectividade, status de serviços
- **Integração**: Acesso a pastas compartilhadas UNC

#### **`crawler_qlik/status_qlik_etl.py`**
- **Função**: Monitoramento de processos ETL
- **Recursos**: Verificação de dependências, integridade de dados, logs de execução
- **Pastas**: Monitora diretórios ETL em servidores de rede

#### **`crawler_qlik/network_config.py`**
- **Função**: Configuração de acesso a pastas compartilhadas de rede
- **Recursos**: Autenticação automática, normalização de caminhos UNC, teste de conectividade
- **Integração**: Usado pelo `send_qlik_evolution.py`

### 📊 **Arquivos de Relatórios PySQL**

#### **`pysql/pysql_homicidios.py`**
- **Função**: Geração completa de relatórios de homicídios
- **Recursos**: Análise temporal, regional, gráficos automáticos, exportação PDF
- **Dados**: Consultas Oracle, processamento pandas, visualizações matplotlib

#### **`pysql/pysql_feminicidio.py`**
- **Função**: Geração de relatórios especializados de feminicídio
- **Recursos**: Análise específica, indicadores, comparações temporais
- **Saída**: PDFs, imagens e dados JSON de execução

### 📱 **Arquivos de Integração WhatsApp**

#### **`evolution_api/send_qlik_evolution.py`**
- **Função**: Envio de relatórios Qlik via WhatsApp
- **Recursos**: Envio individual e em grupo, múltiplos destinos, arquivos PDF
- **Integração**: Usa `network_config.py` para acesso a pastas compartilhadas

#### **`evolution_api/send_pysql_evolution.py`**
- **Função**: Envio de relatórios PySQL via WhatsApp
- **Recursos**: Execução de scripts PySQL, coleta de resumos, envio de relatórios
- **Dados**: Tempos de execução, logs de erro, arquivos PDF

#### **`evolution_api/docker-compose.yaml`**
- **Função**: Configuração Docker para Evolution API
- **Recursos**: Containerização, configuração de rede, volumes persistentes

#### **`evolution_api/env.docker`**
- **Função**: Variáveis de ambiente para container Docker
- **Configurações**: URLs, tokens, instâncias da Evolution API

### 📚 **Arquivos de Documentação**

#### **`technical_documentation/relatorio_webscrepstatusqlik.tex`**
- **Função**: Documentação técnica em LaTeX
- **Conteúdo**: Arquitetura, implementação, configuração do sistema

#### **`technical_documentation/WebScrepStatusQlik__Monitoramento_Automatizado_de_Tarefas_do_Qlik_Sense_com_Envio_de_Alertas_via_WhatsApp.pdf`**
- **Função**: Relatório técnico completo em PDF
- **Conteúdo**: Documentação detalhada do sistema, diagramas, exemplos

### 🎨 **Arquivos de Template e Recursos**

#### **`crawler_qlik/teamplate/template.html`**
- **Função**: Template HTML padrão para relatórios
- **Recursos**: Layout responsivo, estilos CSS, estrutura de dados

#### **`crawler_qlik/teamplate/template_nprinting.html`**
- **Função**: Template específico para relatórios NPrinting
- **Recursos**: Formatação especializada para dados NPrinting

#### **`pysql/img_reports/LogoRelatorio.jpg`**
- **Função**: Logo utilizado nos relatórios PySQL
- **Uso**: Cabeçalho dos relatórios PDF gerados

### 📁 **Pastas de Dados e Logs**

#### **`crawler_qlik/errorlogs/`**
- **Função**: Armazena logs de erro do monitoramento Qlik
- **Conteúdo**: Arquivos de log com detalhes de falhas e problemas

#### **`crawler_qlik/reports_qlik/`**
- **Função**: Armazena relatórios gerados pelo monitoramento
- **Conteúdo**: PDFs, arquivos HTML, dados de status

#### **`pysql/errorlogs/`**
- **Função**: Armazena logs de erro dos scripts PySQL
- **Conteúdo**: Logs de execução, erros de consulta, problemas de conexão

#### **`pysql/reports_pysql/`**
- **Função**: Armazena dados de execução dos relatórios PySQL
- **Conteúdo**: JSONs com tempos de execução, métricas de performance

### 🔧 **Arquivos de Exemplo e Configuração**

#### **`technical_documentation/exemple/`**
- **Função**: Exemplos práticos de uso do sistema
- **Conteúdo**: Scripts de exemplo, configurações, casos de uso

#### **`technical_documentation/img/`**
- **Função**: Recursos visuais da documentação
- **Conteúdo**: Diagramas, screenshots, imagens explicativas

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

