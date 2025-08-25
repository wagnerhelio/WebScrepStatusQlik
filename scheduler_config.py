#!/usr/bin/env python3
"""
Configuração do Scheduler WebScrapStatusQlik

Este arquivo contém todas as configurações do scheduler, permitindo
fácil customização de horários, timeouts e parâmetros de execução.

Para modificar horários ou adicionar novas tarefas, edite este arquivo.
"""

from dataclasses import dataclass
from typing import Dict
from pathlib import Path

@dataclass
class TaskConfig:
    """Configuração de uma tarefa agendada."""
    name: str
    description: str
    script_path: str
    schedule_time: str
    enabled: bool = True
    timeout: int = 300  # 5 minutos padrão
    retry_count: int = 3

# =============================================================================
# CONFIGURAÇÃO DAS TAREFAS
# =============================================================================

# Dicionário com todas as tarefas configuradas
TASKS_CONFIG: Dict[str, TaskConfig] = {
    # Monitoramento de status Qlik (executa a cada hora)
    "status_qlik": TaskConfig(
        name="Status Qlik",
        description="Monitoramento de status Qlik (QMC, NPrinting)",
        script_path="crawler_qlik.status_qlik_task",
        schedule_time=":00",  # A cada hora às XX:00
        timeout=600,  # 10 minutos
        retry_count=3
    ),
    
    # Geração de relatórios PySQL (05:00)
    "reports_pysql": TaskConfig(
        name="Relatórios PySQL",
        description="Geração de relatórios PySQL (homicídios)",
        script_path="pysql.pysql_homicidios",
        schedule_time="05:00",  # 5h da manhã
        timeout=1800,  # 30 minutos
        retry_count=2
    ),
    
    # Monitoramento Qlik Desktop (06:00)
    "status_desktop": TaskConfig(
        name="Status Desktop",
        description="Monitoramento Qlik Sense Desktop",
        script_path="crawler_qlik.status_qlik_desktop",
        schedule_time="06:00",  # 6h da manhã
        timeout=300,  # 5 minutos
        retry_count=3
    ),
    
    # Monitoramento de ETLs (07:00)
    "status_etl": TaskConfig(
        name="Status ETL",
        description="Monitoramento de ETLs",
        script_path="crawler_qlik.status_qlik_etl",
        schedule_time="07:00",  # 7h da manhã
        timeout=300,  # 5 minutos
        retry_count=3
    ),
    
    # Envio de relatórios Qlik (08:00)
    "send_qlik": TaskConfig(
        name="Envio Qlik",
        description="Envio de relatórios Qlik via Evolution API",
        script_path="evolution_api.send_qlik_evolution",
        schedule_time="08:00",  # 8h da manhã
        timeout=900,  # 15 minutos
        retry_count=2
    ),
    
    # Envio de relatórios PySQL (08:05)
    "send_pysql": TaskConfig(
        name="Envio PySQL",
        description="Envio de relatórios PySQL via Evolution API",
        script_path="evolution_api.send_pysql_evolution",
        schedule_time="08:05",  # 8h05 da manhã (5 min após Qlik)
        timeout=900,  # 15 minutos
        retry_count=2
    )
}

# =============================================================================
# CONFIGURAÇÕES GERAIS
# =============================================================================

# Configurações de logging
LOGGING_CONFIG = {
    "log_dir": "logs",
    "log_level": "INFO",
    "log_format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "max_log_files": 30  # Mantém logs dos últimos 30 dias
}

# Configurações de execução
EXECUTION_CONFIG = {
    "check_interval": 30,  # Segundos entre verificações
    "status_interval": 5,  # Minutos entre exibições de status
    "graceful_shutdown": True
}

# =============================================================================
# FUNÇÕES DE UTILIDADE
# =============================================================================

def get_task_config(task_key: str) -> TaskConfig:
    """
    Obtém a configuração de uma tarefa específica.
    
    Args:
        task_key: Chave da tarefa
        
    Returns:
        TaskConfig: Configuração da tarefa
        
    Raises:
        KeyError: Se a tarefa não for encontrada
    """
    if task_key not in TASKS_CONFIG:
        raise KeyError(f"Tarefa '{task_key}' não encontrada na configuração")
    return TASKS_CONFIG[task_key]

def get_enabled_tasks() -> Dict[str, TaskConfig]:
    """
    Obtém apenas as tarefas habilitadas.
    
    Returns:
        Dict[str, TaskConfig]: Dicionário com tarefas habilitadas
    """
    return {key: task for key, task in TASKS_CONFIG.items() if task.enabled}

def get_disabled_tasks() -> Dict[str, TaskConfig]:
    """
    Obtém apenas as tarefas desabilitadas.
    
    Returns:
        Dict[str, TaskConfig]: Dicionário com tarefas desabilitadas
    """
    return {key: task for key, task in TASKS_CONFIG.items() if not task.enabled}

def list_all_tasks() -> None:
    """
    Lista todas as tarefas configuradas no console.
    """
    print("📋 TAREFAS CONFIGURADAS NO SCHEDULER")
    print("=" * 60)
    
    for key, task in TASKS_CONFIG.items():
        status = "✅ HABILITADA" if task.enabled else "⏸️ DESABILITADA"
        print(f"{key}:")
        print(f"  Nome: {task.name}")
        print(f"  Descrição: {task.description}")
        print(f"  Script: {task.script_path}")
        print(f"  Horário: {task.schedule_time}")
        print(f"  Status: {status}")
        print(f"  Timeout: {task.timeout}s")
        print(f"  Retry: {task.retry_count}x")
        print("-" * 40)

if __name__ == "__main__":
    # Se executado diretamente, mostra a configuração
    list_all_tasks()
