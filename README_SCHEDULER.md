# 📅 Scheduler WebScrapStatusQlik

Sistema de agendamento automatizado para monitoramento e envio de relatórios do WebScrapStatusQlik.

## 🚀 Funcionalidades

- **Monitoramento Contínuo**: Status Qlik (QMC, NPrinting) a cada hora
- **Relatórios Diários**: Geração automática de relatórios PySQL
- **Envio Automático**: Distribuição de relatórios via Evolution API
- **Logging Detalhado**: Registro completo de execuções e erros
- **Configuração Flexível**: Horários e parâmetros facilmente ajustáveis
- **Retry Automático**: Tentativas automáticas em caso de falha

## 📋 Tarefas Agendadas

| Tarefa | Horário | Descrição | Timeout |
|--------|---------|-----------|---------|
| **Status Qlik** | A cada hora | Monitoramento QMC e NPrinting | 10 min |
| **Relatórios PySQL** | 05:00 | Geração de relatórios | 30 min |
| **Status Desktop** | 06:00 | Monitoramento Qlik Desktop | 5 min |
| **Status ETL** | 07:00 | Monitoramento de ETLs | 5 min |
| **Envio Qlik** | 08:00 | Envio relatórios Qlik | 15 min |
| **Envio PySQL** | 08:05 | Envio relatórios PySQL | 15 min |

## 🛠️ Instalação e Configuração

### 1. Dependências

```bash
pip install schedule python-dotenv
```

### 2. Configuração

Edite o arquivo `scheduler_config.py` para ajustar:

- **Horários de execução**
- **Timeouts das tarefas**
- **Número de tentativas**
- **Habilitar/desabilitar tarefas**

### 3. Execução

```bash
# Executar o scheduler
python scheduler.py

# Ver configuração atual
python scheduler_config.py
```

## 📁 Estrutura de Arquivos

```
WebScrapStatusQlik/
├── scheduler.py              # Scheduler principal
├── scheduler_config.py       # Configurações
├── README_SCHEDULER.md       # Esta documentação
└── logs/                     # Logs de execução
    └── scheduler_YYYYMMDD.log
```

## ⚙️ Configuração Avançada

### Modificando Horários

Edite `scheduler_config.py`:

```python
"status_qlik": TaskConfig(
    name="Status Qlik",
    description="Monitoramento de status Qlik (QMC, NPrinting)",
    script_path="crawler_qlik.status_qlik_task",
    schedule_time=":30",  # Mudou de ":00" para ":30"
    timeout=600,
    retry_count=3
),
```

### Adicionando Nova Tarefa

```python
"nova_tarefa": TaskConfig(
    name="Nova Tarefa",
    description="Descrição da nova tarefa",
    script_path="modulo.script",
    schedule_time="09:00",  # 9h da manhã
    timeout=300,
    retry_count=3
),
```

### Desabilitando Tarefa

```python
"status_desktop": TaskConfig(
    name="Status Desktop",
    description="Monitoramento Qlik Sense Desktop",
    script_path="crawler_qlik.status_qlik_desktop",
    schedule_time="06:00",
    enabled=False,  # Desabilita a tarefa
    timeout=300,
    retry_count=3
),
```

## 📊 Monitoramento

### Logs de Execução

Os logs são salvos em `logs/scheduler_YYYYMMDD.log` com:

- ✅ Execuções bem-sucedidas
- ❌ Falhas e erros
- ⏰ Timeouts
- 🔄 Tentativas de retry
- 📊 Tempo de execução

### Status em Tempo Real

O scheduler exibe status a cada 5 minutos:

```
================================================================================
📊 STATUS DO SCHEDULER - 14:30:00
================================================================================
✅ Status Qlik              | Próxima execução: 15:00:00
✅ Relatórios PySQL         | Próxima execução: 05:00:00
✅ Status Desktop           | Próxima execução: 06:00:00
✅ Status ETL               | Próxima execução: 07:00:00
✅ Envio Qlik               | Próxima execução: 08:00:00
✅ Envio PySQL              | Próxima execução: 08:05:00
================================================================================
```

## 🔧 Solução de Problemas

### Tarefa Não Executa

1. **Verifique se está habilitada**:
   ```python
   enabled=True  # em scheduler_config.py
   ```

2. **Verifique o script**:
   ```bash
   python -m crawler_qlik.status_qlik_task
   ```

3. **Verifique os logs**:
   ```bash
   tail -f logs/scheduler_20241201.log
   ```

### Timeout Frequente

Aumente o timeout em `scheduler_config.py`:

```python
timeout=1800,  # 30 minutos em vez de 5
```

### Erro de Importação

Verifique se todos os módulos estão acessíveis:

```bash
python -c "import crawler_qlik.status_qlik_task"
python -c "import evolution_api.send_qlik_evolution"
```

## 🚨 Boas Práticas

### 1. Backup de Configuração

```bash
cp scheduler_config.py scheduler_config_backup.py
```

### 2. Teste Antes de Produção

```bash
# Teste uma tarefa específica
python -m crawler_qlik.status_qlik_task
```

### 3. Monitoramento de Logs

```bash
# Monitorar logs em tempo real
tail -f logs/scheduler_$(date +%Y%m%d).log
```

### 4. Reinicialização Segura

```bash
# Parar scheduler (Ctrl+C)
# Aguardar 30 segundos
# Reiniciar
python scheduler.py
```

## 📞 Suporte

Para problemas ou dúvidas:

1. **Verifique os logs** em `logs/`
2. **Teste scripts individualmente**
3. **Verifique configurações** em `scheduler_config.py`
4. **Consulte esta documentação**

---

**Desenvolvido para WebScrapStatusQlik**  
**Versão**: 2.0  
**Data**: Dezembro 2024
