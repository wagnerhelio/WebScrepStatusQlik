# 📦 Guia de Instalação - WebScrapStatusQlik

## 🎯 Visão Geral

Este guia fornece instruções completas para instalar e configurar o projeto WebScrapStatusQlik em diferentes ambientes.

## 📋 Pré-requisitos

### Sistema Operacional
- ✅ Windows 10/11 (Recomendado)
- ✅ Linux (Ubuntu 20.04+)
- ✅ macOS (10.15+)

### Python
- ✅ Python 3.8 ou superior
- ✅ pip (gerenciador de pacotes Python)

### Ferramentas Adicionais
- ✅ Git (para clonar o repositório)
- ✅ Chrome/Chromium (para automação web)
- ✅ Oracle Client (para conexão com banco de dados)

## 🚀 Instalação Passo a Passo

### 1. Clone do Repositório

```bash
git clone https://github.com/seu-usuario/WebScrepStatusQlik.git
cd WebScrepStatusQlik
```

### 2. Criação do Ambiente Virtual

#### Windows (PowerShell)
```powershell
# Criar ambiente virtual
python -m venv venv

# Ativar ambiente virtual
.\venv\Scripts\Activate.ps1

# Se houver erro de política de execução
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

#### Windows (CMD)
```cmd
# Criar ambiente virtual
python -m venv venv

# Ativar ambiente virtual
venv\Scripts\activate.bat
```

#### Linux/macOS
```bash
# Criar ambiente virtual
python3 -m venv venv

# Ativar ambiente virtual
source venv/bin/activate
```

### 3. Instalação das Dependências

```bash
# Atualizar pip
python -m pip install --upgrade pip

# Instalar dependências
pip install -r requirements.txt
```

### 4. Configuração do ChromeDriver

#### Download Automático (Recomendado)
O projeto inclui o ChromeDriver na pasta `crawler_qlik/chromedriver/`.

#### Download Manual
1. Acesse: https://chromedriver.chromium.org/
2. Baixe a versão compatível com seu Chrome
3. Extraia para `crawler_qlik/chromedriver/`

### 5. Configuração das Variáveis de Ambiente

Copie o arquivo de exemplo:
```bash
cp .env_exemple .env
```

Edite o arquivo `.env` com suas configurações:

```env
# =============================================================================
# CONFIGURAÇÕES DO QLIK
# =============================================================================
QLIK_USUARIO=seu_usuario
QLIK_SENHA=sua_senha
QLIK_EMAIL=seu_email@dominio.com

# URLs do Qlik QMC
QLIK_QMC_QAP=https://qlik-qap.dominio.com/qmc
QLIK_TASK_QAP=https://qlik-qap.dominio.com/qmc/tasks
QLIK_QMC_HUB=https://qlik-hub.dominio.com/qmc
QLIK_TASK_HUB=https://qlik-hub.dominio.com/qmc/tasks

# URLs do NPrinting
QLIK_NPRINT=https://nprinting.dominio.com
QLIK_NPRINT_TASK=https://nprinting.dominio.com/tasks

# =============================================================================
# CONFIGURAÇÕES DE BANCO DE DADOS
# =============================================================================
DB_HOST=servidor_banco
DB_PORT=1521
DB_SERVICE=servico_banco
DB_USER=usuario_banco
DB_PASSWORD=senha_banco

# =============================================================================
# CONFIGURAÇÕES DA EVOLUTION API
# =============================================================================
EVOLUTION_API_TOKEN=seu_token_api
EVOLUTION_INSTANCE_NAME=nome_instancia
EVOLUTION_INSTANCE_ID=id_instancia
EVO_DESTINO_GRUPO=grupo_destino
EVO_DESTINO=numero_destino

# =============================================================================
# CONFIGURAÇÕES DE REDE (OPCIONAL)
# =============================================================================
NETWORK_USERNAME=usuario_rede
NETWORK_PASSWORD=senha_rede
NETWORK_DOMAIN=dominio_rede

# =============================================================================
# CONFIGURAÇÕES DE DIRETÓRIOS
# =============================================================================
CHROMEDRIVER=crawler_qlik/chromedriver/chromedriver.exe
TASKS_DIR=crawler_qlik/reports_qlik
```

## 🔧 Configurações Específicas por Sistema

### Windows

#### Configuração do Oracle Client
1. Baixe o Oracle Instant Client: https://www.oracle.com/database/technologies/instant-client/downloads.html
2. Extraia para `C:\oracle\instantclient_21_x`
3. Adicione ao PATH: `C:\oracle\instantclient_21_x`

#### Configuração do Chrome
```powershell
# Verificar versão do Chrome
(Get-Item "C:\Program Files\Google\Chrome\Application\chrome.exe").VersionInfo.FileVersion
```

### Linux (Ubuntu/Debian)

#### Instalação de Dependências do Sistema
```bash
sudo apt update
sudo apt install -y \
    python3-pip \
    python3-venv \
    chromium-browser \
    libgconf-2-4 \
    libnss3 \
    libxss1 \
    libasound2 \
    libatk-bridge2.0-0 \
    libgtk-3-0 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libasound2
```

#### Configuração do Oracle Client
```bash
# Baixar Oracle Instant Client
wget https://download.oracle.com/otn_software/linux/instantclient/219000/instantclient-basic-linux.x64-21.9.0.0.0.zip
unzip instantclient-basic-linux.x64-21.9.0.0.0.zip

# Configurar variáveis de ambiente
export LD_LIBRARY_PATH=/path/to/instantclient_21_9:$LD_LIBRARY_PATH
```

### macOS

#### Instalação via Homebrew
```bash
# Instalar Homebrew (se não tiver)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Instalar dependências
brew install python3
brew install --cask google-chrome
brew install --cask oracle-instantclient
```

## 🧪 Teste de Instalação

### 1. Teste de Dependências Python
```bash
python -c "import selenium, pandas, oracledb, evolutionapi; print('✅ Todas as dependências instaladas!')"
```

### 2. Teste do ChromeDriver
```bash
python crawler_qlik/network_config.py
```

### 3. Teste de Conectividade de Rede
```bash
python teste_caminhos_unc.py
```

### 4. Teste dos Scripts Principais
```bash
# Teste do status do Qlik Desktop
python crawler_qlik/status_qlik_desktop.py

# Teste do status das ETLs
python crawler_qlik/status_qlik_etl.py

# Teste do envio via Evolution API
python evolution_api/send_qlik_evolution.py
```

## 🔍 Solução de Problemas

### Erro: "ChromeDriver não encontrado"
```bash
# Verificar se o ChromeDriver está no PATH
where chromedriver  # Windows
which chromedriver  # Linux/macOS

# Definir caminho manualmente no .env
CHROMEDRIVER=caminho/completo/para/chromedriver
```

### Erro: "Oracle Client não encontrado"
```bash
# Windows: Verificar se o Oracle Client está no PATH
echo $env:PATH | Select-String "oracle"

# Linux: Verificar variáveis de ambiente
echo $LD_LIBRARY_PATH
```

### Erro: "Módulo não encontrado"
```bash
# Verificar se o ambiente virtual está ativo
# Windows
echo $env:VIRTUAL_ENV

# Linux/macOS
echo $VIRTUAL_ENV

# Reinstalar dependências
pip install -r requirements.txt --force-reinstall
```

### Erro: "Permissão negada"
```bash
# Linux/macOS: Dar permissão de execução
chmod +x crawler_qlik/chromedriver/chromedriver

# Windows: Executar como administrador
```

## 📚 Recursos Adicionais

### Documentação
- [Solução de Erros de Rede](SOLUCAO_ERRO_REDE.md)
- [README Principal](README.md)
- [Documentação do Scheduler](README_SCHEDULER.md)

### Links Úteis
- [Selenium Documentation](https://selenium-python.readthedocs.io/)
- [Oracle Python Driver](https://python-oracledb.readthedocs.io/)
- [Evolution API](https://doc.evolution-api.com/)

## 🤝 Suporte

Se encontrar problemas durante a instalação:

1. **Verifique os logs de erro**
2. **Consulte a documentação**
3. **Teste em um ambiente limpo**
4. **Abra uma issue no GitHub**

## ✅ Checklist de Instalação

- [ ] Python 3.8+ instalado
- [ ] Ambiente virtual criado e ativado
- [ ] Dependências instaladas (`pip install -r requirements.txt`)
- [ ] ChromeDriver configurado
- [ ] Oracle Client configurado (se necessário)
- [ ] Arquivo `.env` configurado
- [ ] Testes executados com sucesso
- [ ] Scripts principais funcionando

---

**🎉 Parabéns! Seu ambiente está configurado e pronto para uso.**
