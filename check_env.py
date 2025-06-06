import os
import subprocess
from dotenv import load_dotenv

# Carrega o .env
load_dotenv()

erros = []

# Verifica variáveis obrigatórias
usuario = os.getenv("QLIK_USUARIO")
senha = os.getenv("QLIK_SENHA")
chromedriver = os.getenv("CHROMEDRIVER")

# 1. Verificações
if not usuario:
    erros.append("❌ QLIK_USUARIO não encontrado no .env.")
elif "\\" not in usuario:
    erros.append("⚠️ QLIK_USUARIO deve conter '\\\\' para escapar a barra invertida (ex: dominio\\\\usuario).")

if not senha:
    erros.append("❌ QLIK_SENHA não encontrado no .env.")

if not chromedriver:
    erros.append("❌ CHROMEDRIVER não encontrado no .env.")
elif not os.path.isfile(chromedriver):
    erros.append(f"❌ Caminho para CHROMEDRIVER inválido: {chromedriver}")

# 2. Exibe resultado
if erros:
    print("🚫 Problemas encontrados no arquivo .env:\n")
    for erro in erros:
        print(" -", erro)
    print("\nCorrija os erros acima e tente novamente.")
else:
    print("✅ .env validado com sucesso!")
    print(f"🔐 Usuário carregado: {usuario}")
    print(f"📁 Caminho do chromedriver: {chromedriver}")
    
    # 3. Executa statusqlik.py
    print("\n🚀 Executando statusqlik.py...")
    subprocess.run(["python", "statusqlik.py"])
