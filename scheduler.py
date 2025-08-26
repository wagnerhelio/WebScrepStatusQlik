#!/usr/bin/env python3
"""
Scheduler Simplificado para WebScrapStatusQlik

Este módulo gerencia a execução automática de scripts de monitoramento e envio
de relatórios do sistema WebScrapStatusQlik.

Cronograma:
- A cada hora: Monitoramento de status Qlik (QMC, NPrinting)
- 12:00 PM: Envio de relatórios Qlik via Evolution API
- Após envio Qlik: Envio de relatórios PySQL via Evolution API

Funcionalidades:
- Execução sequencial de tarefas (sem horários fixos)
- Monitoramento de status Qlik a cada hora
- Envio automático de relatórios via Evolution API
- Logging detalhado de execução
- Retry automático em caso de falhas

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
from typing import Dict, List, Optional
from dataclasses import dataclass

# Configuração para Windows - suporte a UTF-8
if os.name == 'nt':  # Windows
    try:
        # Tenta configurar o console para UTF-8
        os.system('chcp 65001 > nul')
    except:
        pass

# =============================================================================
# CONFIGURAÇÃO DAS TAREFAS
# =============================================================================

@dataclass
class TaskConfig:
    """Configuração de uma tarefa agendada."""
    name: str
    description: str
    script_path: str
    enabled: bool = True
    timeout: int = 300  # 5 minutos padrão
    retry_count: int = 3

# Configuração das tarefas
TASKS = {
    # Monitoramento de status Qlik (executa a cada hora)
    "status_qlik": TaskConfig(
        name="Status Qlik",
        description="Monitoramento de status Qlik (QMC, NPrinting)",
        script_path="crawler_qlik.status_qlik_task",
        timeout=600,  # 10 minutos
        retry_count=3
    ),
    
    # Envio de relatórios Qlik (08:00)
    "send_qlik": TaskConfig(
        name="Envio Qlik",
        description="Envio de relatórios Qlik via Evolution API",
        script_path="evolution_api.send_qlik_evolution",
        timeout=900,  # 15 minutos
        retry_count=2
    ),
    
    # Envio de relatórios PySQL (após Qlik)
    "send_pysql": TaskConfig(
        name="Envio PySQL",
        description="Envio de relatórios PySQL via Evolution API",
        script_path="evolution_api.send_pysql_evolution",
        timeout=900,  # 15 minutos
        retry_count=2
    )
}

# =============================================================================
# CONFIGURAÇÕES GERAIS
# =============================================================================

# Configurações de logging
LOG_DIR = "scheduler_logs"
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Configurações de execução
CHECK_INTERVAL = 30  # Segundos entre verificações
STATUS_INTERVAL = 5  # Minutos entre exibições de status

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
    log_dir = Path(LOG_DIR)
    log_dir.mkdir(exist_ok=True)
    
    # Configura o logger
    logger = logging.getLogger("WebScrapScheduler")
    logger.setLevel(getattr(logging, LOG_LEVEL))
    
    # Limpa handlers existentes
    logger.handlers.clear()
    
    # Handler para arquivo
    file_handler = logging.FileHandler(
        log_dir / f"scheduler_{datetime.now().strftime('%Y%m%d')}.log",
        encoding='utf-8'
    )
    file_handler.setLevel(getattr(logging, LOG_LEVEL))
    
    # Handler para console
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, LOG_LEVEL))
    
    # Formato das mensagens
    formatter = logging.Formatter(LOG_FORMAT)
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
    
    def check_script_encoding(self, script_path: str) -> bool:
        """
        Verifica se o script tem problemas de codificação.
        
        Args:
            script_path: Caminho do script a ser verificado
            
        Returns:
            bool: True se o script está OK, False se há problemas
        """
        try:
            # Converte o caminho do módulo para caminho de arquivo
            module_parts = script_path.split('.')
            script_file = self.project_root / '/'.join(module_parts) + '.py'
            
            if not script_file.exists():
                self.logger.warning(f"   ⚠️ Arquivo não encontrado: {script_file}")
                return False
            
            # Tenta ler o arquivo com diferentes codificações
            encodings = ['utf-8', 'cp1252', 'latin-1']
            
            for encoding in encodings:
                try:
                    with open(script_file, 'r', encoding=encoding) as f:
                        content = f.read()
                        # Verifica se há emojis problemáticos
                        if any(ord(char) > 127 for char in content):
                            self.logger.info(f"   📝 Script usa caracteres especiais (codificação: {encoding})")
                        return True
                except UnicodeDecodeError:
                    continue
            
            self.logger.warning(f"   ⚠️ Não foi possível ler o arquivo com nenhuma codificação")
            return False
            
        except Exception as e:
            self.logger.warning(f"   ⚠️ Erro ao verificar codificação: {e}")
            return True  # Assume que está OK se não conseguir verificar
    
    def execute_task(self, task_key: str) -> bool:
        """
        Executa uma tarefa específica com retry e logging.
        
        Args:
            task_key: Chave da tarefa na configuração
            
        Returns:
            bool: True se executou com sucesso, False caso contrário
        """
        task = TASKS.get(task_key)
        if not task or not task.enabled:
            self.logger.warning(f"Tarefa {task_key} não encontrada ou desabilitada")
            return False
        
        self.logger.info(f"🚀 Iniciando execução: {task.name}")
        self.logger.info(f"   📝 Descrição: {task.description}")
        self.logger.info(f"   📁 Script: {task.script_path}")
        self.logger.info(f"   ⏰ Timeout: {task.timeout}s")
        
        # Verifica codificação do script
        self.check_script_encoding(task.script_path)
        
        start_time = datetime.now()
        success = False
        error_message = ""
        
        # Tenta executar com retry
        for attempt in range(task.retry_count):
            try:
                self.logger.info(f"   🔄 Tentativa {attempt + 1}/{task.retry_count}")
                
                # Executa o script com codificação UTF-8 para evitar problemas com emojis
                env = os.environ.copy()
                env['PYTHONIOENCODING'] = 'utf-8'
                
                # Para scripts PySQL e Qlik, não captura saída para mostrar progresso em tempo real
                if task_key in ["send_pysql", "send_qlik"]:
                    result = subprocess.run(
                        [self.python_exec, "-m", task.script_path],
                        capture_output=False,  # Permite que a saída apareça no terminal
                        text=True,
                        encoding='utf-8',
                        timeout=task.timeout,
                        cwd=self.project_root,
                        env=env
                    )
                else:
                    result = subprocess.run(
                        [self.python_exec, "-m", task.script_path],
                        capture_output=True,
                        text=True,
                        encoding='utf-8',
                        timeout=task.timeout,
                        cwd=self.project_root,
                        env=env
                    )
                
                if result.returncode == 0:
                    success = True
                    self.logger.info(f"✅ {task.name} executado com sucesso")
                    if result.stdout.strip():
                        self.logger.debug(f"   📤 Saída: {result.stdout.strip()}")
                    break
                else:
                    # Trata erros de codificação especificamente
                    stderr_output = result.stderr.strip()
                    if "UnicodeEncodeError" in stderr_output or "charmap" in stderr_output:
                        error_message = f"Erro de codificação Unicode - verifique se o script suporta UTF-8"
                        self.logger.warning(f"   ⚠️ Tentativa {attempt + 1} falhou: {error_message}")
                        self.logger.debug(f"   📋 Detalhes: {stderr_output[:200]}...")
                    else:
                        error_message = f"Código de retorno {result.returncode}: {stderr_output}"
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
        self.last_hourly_run = None
        self.last_daily_run = None
        
        self.logger.info("🔧 Inicializando WebScrapScheduler")
        self.logger.info(f"   🐍 Python: {self.executor.python_exec}")
        self.logger.info(f"   📁 Projeto: {self.executor.project_root}")
    
    def should_run_hourly_task(self) -> bool:
        """
        Verifica se deve executar a tarefa horária (status Qlik).
        
        Returns:
            bool: True se deve executar, False caso contrário
        """
        now = datetime.now()
        
        # Se nunca executou, executa imediatamente
        if self.last_hourly_run is None:
            return True
        
        # Verifica se passou pelo menos 1 hora desde a última execução
        time_diff = now - self.last_hourly_run
        return time_diff.total_seconds() >= 3600  # 1 hora
    
    def should_run_daily_tasks(self) -> bool:
        """
        Verifica se deve executar as tarefas diárias (envio de relatórios).
        
        Returns:
            bool: True se deve executar, False caso contrário
        """
        now = datetime.now()
        
        # Executa às 12:00
        if now.hour == 13 and now.minute == 22:
            # Verifica se já executou hoje
            if self.last_daily_run is None or self.last_daily_run.date() != now.date():
                return True
        
        return False
    
    def run_hourly_task(self):
        """Executa a tarefa horária (status Qlik)."""
        self.logger.info("🕐 Executando tarefa horária: Status Qlik")
        success = self.executor.execute_task("status_qlik")
        if success:
            self.last_hourly_run = datetime.now()
            self.logger.info("✅ Tarefa horária concluída com sucesso")
        else:
            self.logger.error("❌ Tarefa horária falhou")
    
    def run_daily_tasks(self):
        """Executa as tarefas diárias sequencialmente."""
        self.logger.info("🌅 Executando tarefas diárias: Envio de relatórios")
        
        # 1. Envia relatórios Qlik
        self.logger.info("📤 Iniciando envio de relatórios Qlik...")
        success_qlik = self.executor.execute_task("send_qlik")
        
        if success_qlik:
            self.logger.info("✅ Envio Qlik concluído, iniciando PySQL...")
            
            # 2. Envia relatórios PySQL (após Qlik)
            self.logger.info("📤 Iniciando envio de relatórios PySQL...")
            success_pysql = self.executor.execute_task("send_pysql")
            
            if success_pysql:
                self.logger.info("✅ Todas as tarefas diárias concluídas com sucesso")
                self.last_daily_run = datetime.now()
            else:
                self.logger.error("❌ Envio PySQL falhou")
        else:
            self.logger.error("❌ Envio Qlik falhou, PySQL não será executado")
    
    def print_status(self):
        """Imprime o status atual do scheduler."""
        now = datetime.now().strftime("%H:%M:%S")
        
        print(f"\n{'='*80}")
        print(f"📊 STATUS DO SCHEDULER - {now}")
        print(f"{'='*80}")
        
        # Status das tarefas
        for task_key, task in TASKS.items():
            status = "✅" if task.enabled else "⏸️"
            print(f"{status} {task.name:<20} | {task.description}")
        
        # Status das execuções
        print(f"\n📈 ÚLTIMAS EXECUÇÕES:")
        if self.last_hourly_run:
            print(f"   🕐 Status Qlik: {self.last_hourly_run.strftime('%d/%m/%Y %H:%M:%S')}")
        else:
            print(f"   🕐 Status Qlik: Nunca executado")
            
        if self.last_daily_run:
            print(f"   🌅 Relatórios: {self.last_daily_run.strftime('%d/%m/%Y %H:%M:%S')}")
        else:
            print(f"   🌅 Relatórios: Nunca executado")
        
        print(f"{'='*80}")
    
    def run(self):
        """Executa o scheduler principal."""
        self.logger.info("🚀 Iniciando WebScrapScheduler")
        self.logger.info("📅 Cronograma configurado:")
        self.logger.info("   🕐 A cada hora: Status Qlik")
        self.logger.info("   🌅 08:00 AM: Envio Qlik → Envio PySQL")
        
        self.running = True
        self.logger.info("✅ Scheduler iniciado. Pressione Ctrl+C para sair.")
        
        try:
            while self.running:
                # Verifica tarefa horária
                if self.should_run_hourly_task():
                    self.run_hourly_task()
                
                # Verifica tarefas diárias
                if self.should_run_daily_tasks():
                    self.run_daily_tasks()
                
                # Aguarda próximo ciclo
                time.sleep(CHECK_INTERVAL)
                
                # Mostra status a cada X minutos
                if (datetime.now().minute % STATUS_INTERVAL == 0 and 
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