# WebScrepStatusQlik
Crawler e WebScrep Qlik Sense Status Task
## ✅ Requisitos
- Python 3.10+
- Git

## 🚀 Instalação

## Instalações Recomendadas no Ambiente 
``` bash
ms-python.vscode-python-envs
```
https://visualstudio.microsoft.com/visual-cpp-build-tools/
Clique em “Download Build Tools”.

Na instalação, selecione “C++ build tools”.

Marque também a opção “Windows 10 SDK” ou “Windows 11 SDK”, conforme seu sistema.

## Comandos Recorrentes de Desenvolvimento 

```bash
git clone https://github.com/wagnerhelio/WebScrepStatusQlik.git
```

```bash
python -m venv venv
```

```bash
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
```

```bash
.\.venv\Scripts\Activate
```

```bash
pip install -r requirements.txt
```
Baixe o WebDriver compativel com seu Google Chrome:
https://edgedl.me.gvt1.com/edgedl/chrome/chrome-for-testing/137.0.7151.69/win64/chromedriver-win64.zip

configure o arquivo .env_exemple renomeando para .env

execute para obter os arquivos do monitoramento de logs.
```bash
python .\statusqlik.py 
``` 
## para enviar via Whats App os logs.

Siga os passos de configuração do Evolution API
https://doc.evolution-api.com/v1/pt/get-started/introduction

```bash
python .\send_statusqlik_evolution.py
```
![WebScrep_QMC.drawio](WebScrep_QMC.drawio.png)