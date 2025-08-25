#!/usr/bin/env python3
"""
Scheduler para automação de tarefas WebScrapStatusQlik

Este módulo gerencia a execução automática de scripts de monitoramento e envio
de relatórios do sistema WebScrapStatusQlik.

Funcionalidades:
- Monitoramento de status Qlik (QMC, NPrinting, Desktop, ETL) a cada hora
- Geração de relatórios PySQL diários
- Envio automático de relatórios via Evolution API
- Logging detalhado de execução
- Configuração centralizada de horários

Autor: Sistema WebScrapStatusQlik
Data: 2024
"""

import schedule
import time
import subprocess
import logging
import sys
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Callable
import glob

# Importa configurações
from scheduler_config import TASKS_CONFIG, LOGGING_CONFIG, EXECUTION_CONFIG

# =============================================================================
# CONFIGURAÇÃO DE LOGGING
# =============================================================================

def setup_logging() -> logging.Logger:
    """
    Configura o sistema de logging para o scheduler.
    
    Returns:
        logging.Logger: Logger configurado
    """
    # Cria diretório de logs se não existir
    log_dir = Path(LOGGING_CONFIG["log_dir"])
    log_dir.mkdir(exist_ok=True)
    
    # Configura o logger
    logger = logging.getLogger("WebScrapScheduler")
    logger.setLevel(getattr(logging, LOGGING_CONFIG["log_level"]))
    
    # Limpa handlers existentes
    logger.handlers.clear()
    
    # Handler para arquivo
    file_handler = logging.FileHandler(
        log_dir / f"scheduler_{datetime.now().strftime('%Y%m%d')}.log",
        encoding='utf-8'
    )
    file_handler.setLevel(getattr(logging, LOGGING_CONFIG["log_level"]))
    
    # Handler para console
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, LOGGING_CONFIG["log_level"]))
    
    # Formato das mensagens
    formatter = logging.Formatter(LOGGING_CONFIG["log_format"])
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # Adiciona handlers ao logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

# =============================================================================
# EXECUTOR DE TAREFAS
# =============================================================================

class TaskExecutor:
    """Executor de tarefas com retry e logging."""
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self.python_exec = sys.executable
        self.project_root = Path(__file__).parent
        self.execution_history: List[Dict] = []
    
    def execute_task(self, task_key: str) -> bool:
        """
        Executa uma tarefa específica com retry e logging.
        
        Args:
            task_key: Chave da tarefa na configuração
            
        Returns:
            bool: True se executou com sucesso, False caso contrário
        """
        task = TASKS_CONFIG.get(task_key)
        if not task or not task.enabled:
            self.logger.warning(f"Tarefa {task_key} não encontrada ou desabilitada")
            return False
        
        self.logger.info(f"🚀 Iniciando execução: {task.name}")
        self.logger.info(f"   📝 Descrição: {task.description}")
        self.logger.info(f"   📁 Script: {task.script_path}")
        self.logger.info(f"   ⏰ Timeout: {task.timeout}s")
        
        start_time = datetime.now()
        success = False
        error_message = ""
        
        # Tenta executar com retry
        for attempt in range(task.retry_count):
            try:
                self.logger.info(f"   🔄 Tentativa {attempt + 1}/{task.retry_count}")
                
                # Executa o script
                result = subprocess.run(
                    [self.python_exec, "-m", task.script_path],
                    capture_output=True,
                    text=True,
                    timeout=task.timeout,
                    cwd=self.project_root
                )
                
                if result.returncode == 0:
                    success = True
                    self.logger.info(f"✅ {task.name} executado com sucesso")
                    if result.stdout.strip():
                        self.logger.debug(f"   📤 Saída: {result.stdout.strip()}")
                    break
                else:
                    error_message = f"Código de retorno {result.returncode}: {result.stderr.strip()}"
                    self.logger.warning(f"   ⚠️ Tentativa {attempt + 1} falhou: {error_message}")
                    
            except subprocess.TimeoutExpired:
                error_message = f"Timeout após {task.timeout}s"
                self.logger.error(f"   ⏰ Tentativa {attempt + 1} expirou: {error_message}")
            except Exception as e:
                error_message = str(e)
                self.logger.error(f"   ❌ Tentativa {attempt + 1} com erro: {error_message}")
        
        # Registra resultado
        execution_time = (datetime.now() - start_time).total_seconds()
        self.execution_history.append({
            "task": task_key,
            "name": task.name,
            "start_time": start_time,
            "execution_time": execution_time,
            "success": success,
            "error": error_message if not success else None
        })
        
        if success:
            self.logger.info(f"✅ {task.name} finalizado em {execution_time:.2f}s")
        else:
            self.logger.error(f"❌ {task.name} falhou após {task.retry_count} tentativas")
            self.logger.error(f"   💬 Último erro: {error_message}")
        
        return success

# =============================================================================
# AGENDADOR PRINCIPAL
# =============================================================================

class WebScrapScheduler:
    """Agendador principal do sistema WebScrapStatusQlik."""
    
    def __init__(self):
        self.logger = setup_logging()
        self.executor = TaskExecutor(self.logger)
        self.running = False
        
        self.logger.info("🔧 Inicializando WebScrapScheduler")
        self.logger.info(f"   🐍 Python: {self.executor.python_exec}")
        self.logger.info(f"   📁 Projeto: {self.executor.project_root}")
    
    def setup_schedule(self):
        """Configura o agendamento das tarefas."""
        self.logger.info("📅 Configurando agendamento das tarefas...")
        
        for task_key, task in TASKS_CONFIG.items():
            if not task.enabled:
                self.logger.info(f"   ⏸️ {task.name} - DESABILITADA")
                continue
            
            # Cria função wrapper para a tarefa
            def create_task_wrapper(task_key):
                def task_wrapper():
                    self.executor.execute_task(task_key)
                task_wrapper.__name__ = f"task_wrapper_{task_key}"
                return task_wrapper
            
            # Configura o agendamento
            if task.schedule_time.startswith(":"):
                # A cada hora
                schedule.every().hour.at(task.schedule_time).do(create_task_wrapper(task_key))
                self.logger.info(f"   🔄 {task.name} - A cada hora às {task.schedule_time}")
            else:
                # Horário específico
                schedule.every().day.at(task.schedule_time).do(create_task_wrapper(task_key))
                self.logger.info(f"   📅 {task.name} - Diário às {task.schedule_time}")
    
    def get_next_runs(self) -> Dict[str, str]:
        """Obtém os próximos horários de execução de todas as tarefas."""
        next_runs = {}
        
        for task_key, task in TASKS_CONFIG.items():
            if not task.enabled:
                next_runs[task_key] = "DESABILITADA"
                continue
            
            jobs = [job for job in schedule.get_jobs() 
                   if getattr(job.job_func, "__name__", "") == f"task_wrapper_{task_key}"]
            
            if jobs and jobs[0].next_run:
                next_runs[task_key] = jobs[0].next_run.strftime("%H:%M:%S")
            else:
                next_runs[task_key] = "N/A"
        
        return next_runs
    
    def print_status(self):
        """Imprime o status atual do scheduler."""
        now = datetime.now().strftime("%H:%M:%S")
        next_runs = self.get_next_runs()
        
        print(f"\n{'='*80}")
        print(f"📊 STATUS DO SCHEDULER - {now}")
        print(f"{'='*80}")
        
        for task_key, task in TASKS_CONFIG.items():
            status = "✅" if task.enabled else "⏸️"
            next_run = next_runs.get(task_key, "N/A")
            print(f"{status} {task.name:<20} | Próxima execução: {next_run}")
        
        print(f"{'='*80}")
    
    def run(self):
        """Executa o scheduler principal."""
        self.logger.info("🚀 Iniciando WebScrapScheduler")
        self.setup_schedule()
        
        self.running = True
        self.logger.info("✅ Scheduler iniciado. Pressione Ctrl+C para sair.")
        
        try:
            while self.running:
                schedule.run_pending()
                time.sleep(EXECUTION_CONFIG["check_interval"])
                
                # Mostra status a cada X minutos
                if (datetime.now().minute % EXECUTION_CONFIG["status_interval"] == 0 and 
                    datetime.now().second < 30):
                    self.print_status()
                    
        except KeyboardInterrupt:
            self.logger.info("🛑 Scheduler interrompido pelo usuário")
        except Exception as e:
            self.logger.error(f"❌ Erro no scheduler: {e}")
            raise
        finally:
            self.running = False
            self.logger.info("🏁 Scheduler finalizado")

# =============================================================================
# FUNÇÃO PRINCIPAL
# =============================================================================

def main():
    """Função principal do scheduler."""
    scheduler = WebScrapScheduler()
    scheduler.run()

if __name__ == "__main__":
    main()