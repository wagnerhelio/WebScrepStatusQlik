#!/usr/bin/env python3
"""
Scheduler Simples para WebScrapStatusQlik

Executa automaticamente:
- A cada hora: Status Qlik
- 08:00 AM: Envio Qlik → Envio PySQL
"""

import time
import subprocess
import os
from datetime import datetime
from pathlib import Path
import sys

# Configuração UTF-8 para Windows
if os.name == 'nt':
    os.system('chcp 65001 > nul')

def executar_tarefa(script, descricao):
    """Executa uma tarefa com retry."""
    for tentativa in range(3):
        try:
            print(f"Executando {descricao} (tentativa {tentativa + 1}/3)")
            
            result = subprocess.run(
                [sys.executable, '-m', script],
                capture_output=False,
                # SEM timeout para PySQL - permite que as consultas demorem o tempo necessário
                cwd=Path(__file__).parent,
                env={**os.environ, 'PYTHONIOENCODING': 'utf-8'}
            )
            
            if result.returncode == 0:
                print(f"✅ {descricao} executado com sucesso")
                return True
            else:
                print(f"❌ {descricao} falhou (código {result.returncode})")
                
        except subprocess.TimeoutExpired:
            print(f"⏰ {descricao} expirou")
        except KeyboardInterrupt:
            print(f"⚠️ {descricao} foi interrompido pelo usuário - continuando...")
            return False  # Retorna False mas não para o scheduler
        except Exception as e:
            print(f"❌ {descricao} erro: {e}")
    
    print(f"❌ {descricao} falhou após 3 tentativas")
    return False

def main():
    """Função principal do scheduler."""
    print("🚀 Scheduler iniciado")
    
    ultima_hora = None
    ultimo_dia = None
    
    try:
        while True:
            agora = datetime.now()
            
            # Tarefa horária (a cada hora)
            if ultima_hora is None or (agora - ultima_hora).total_seconds() >= 3600:
                print("🕐 Executando tarefa horária: Status Qlik")
                if executar_tarefa("crawler_qlik.status_qlik_task", "Status Qlik"):
                    ultima_hora = agora
            
            # Tarefas diárias (08:00)
            if (agora.hour == 8 and agora.minute == 0 and 
                (ultimo_dia is None or ultimo_dia.date() != agora.date())):
                
                print("🌅 Executando tarefas diárias")
                
                # Envio Qlik
                executar_tarefa("evolution_api.send_qlik_evolution", "Envio Qlik")
                
                # Envio PySQL (após Qlik) - sempre executa, mesmo se Qlik falhar
                executar_tarefa("evolution_api.send_pysql_evolution", "Envio PySQL")
                ultimo_dia = agora
            
            time.sleep(30)  # Verifica a cada 30 segundos
            
    except KeyboardInterrupt:
        print("🛑 Scheduler interrompido")
    except Exception as e:
        print(f"❌ Erro no scheduler: {e}")

if __name__ == "__main__":
    main()