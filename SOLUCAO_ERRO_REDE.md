# 🔧 Solução para Erro de Autenticação de Rede

## 📋 Problema Identificado

O erro `[WinError 1326] Nome de usuário ou senha incorretos` ocorre quando o script tenta acessar pastas de rede (UNC paths) que requerem credenciais específicas de autenticação.

### Problema Adicional: Interpretação Incorreta de Caminhos UNC
Em algumas máquinas, os caminhos UNC estavam sendo interpretados incorretamente com barras duplas extras (`\\\\`), causando erros de acesso.

### Pastas afetadas:
- `\\10.242.251.28\SSPForcas$\SSP_FORCAS_BI`
- `\\Arquivos-02\Business Intelligence\Qlik Sense Desktop`
- `\\estatistica\Repositorio\ETL`

## ✅ Soluções Implementadas

### 1. Tratamento de Erros Robusto
- Os scripts agora detectam erros de autenticação e continuam funcionando
- Pastas inacessíveis são puladas com mensagens informativas
- O processo não para completamente quando há problemas de rede

### 2. Configuração de Credenciais de Rede
- Novo módulo `network_config.py` para gerenciar credenciais
- Suporte a variáveis de ambiente para configuração segura
- Teste automático de conectividade de rede

### 3. Normalização de Caminhos UNC
- Função `normalize_unc_path()` para corrigir interpretação de caminhos
- Conversão automática de barras duplas para formato correto
- Compatibilidade entre diferentes sistemas operacionais

## 🚀 Como Resolver

### Opção 1: Configurar Credenciais (Recomendado)

1. **Configure as variáveis de ambiente:**

```bash
# Windows (PowerShell)
$env:NETWORK_USERNAME="seu_usuario"
$env:NETWORK_PASSWORD="sua_senha"
$env:NETWORK_DOMAIN="seu_dominio"  # opcional

# Windows (CMD)
set NETWORK_USERNAME=seu_usuario
set NETWORK_PASSWORD=sua_senha
set NETWORK_DOMAIN=seu_dominio

# Linux/Mac
export NETWORK_USERNAME="seu_usuario"
export NETWORK_PASSWORD="sua_senha"
export NETWORK_DOMAIN="seu_dominio"
```

2. **Teste a configuração:**

```bash
python crawler_qlik/network_config.py
```

3. **Execute o script principal:**

```bash
python evolution_api/send_qlik_evolution.py
```

### Opção 2: Executar sem Acesso de Rede

Se você não tem as credenciais de rede, o script continuará funcionando:

- ✅ Status do NPrinting (relatórios)
- ✅ Status do QMC (estatísticas e painéis)
- ❌ Status do Qlik Desktop (requer acesso de rede)
- ❌ Status das ETLs (requer acesso de rede)

### Opção 3: Mapear Unidades de Rede Manualmente

1. **Abra o Windows Explorer**
2. **Digite o caminho UNC:** `\\10.242.251.28\SSPForcas$`
3. **Insira suas credenciais quando solicitado**
4. **Repita para outras pastas se necessário**

## 🔍 Verificação de Status

### Teste de Conectividade

```bash
# Testa acesso às pastas de rede
python crawler_qlik/network_config.py
```

### Verificação Manual

```bash
# Testa cada script individualmente
python crawler_qlik/status_qlik_desktop.py
python crawler_qlik/status_qlik_etl.py
```

## 📊 Mensagens de Status

### ✅ Sucesso
```
✅ Diretório acessível: \\10.242.251.28\SSPForcas$\SSP_FORCAS_BI
✅ Credenciais configuradas para: \\10.242.251.28\SSPForcas$\SSP_FORCAS_BI
```

### ⚠️ Avisos
```
⚠️ Erro de autenticação ao acessar pasta: \\10.242.251.28\SSPForcas$\SSP_FORCAS_BI
   A pasta requer credenciais específicas de rede.
   Pulando esta pasta e continuando...
```

### ❌ Erros
```
❌ Diretório inacessível: \\10.242.251.28\SSPForcas$\SSP_FORCAS_BI
```

## 🛠️ Troubleshooting

### Problema: "Acesso negado"
- Verifique se o usuário tem permissões na pasta
- Confirme se o domínio está correto
- Teste o acesso via Windows Explorer

### Problema: "Caminho de rede não encontrado"
- Verifique se o servidor está online
- Confirme se o caminho UNC está correto
- Teste conectividade de rede

### Problema: "Nome de usuário ou senha incorretos"
- Verifique as credenciais
- Confirme se a conta não está bloqueada
- Teste login em outras máquinas

### Problema: Caminhos com barras duplas extras (`\\\\`)
- **SOLUCIONADO**: Implementada normalização automática de caminhos
- Os scripts agora corrigem automaticamente a interpretação de caminhos UNC
- Compatível com diferentes versões do Windows

## 📞 Suporte

Se o problema persistir:

1. **Colete informações:**
   - Saída completa do erro
   - Resultado do teste de rede
   - Configurações de ambiente

2. **Verifique:**
   - Políticas de segurança da rede
   - Firewall e antivírus
   - Configurações de domínio

3. **Contate o administrador de rede** para:
   - Verificar permissões de usuário
   - Confirmar acesso às pastas compartilhadas
   - Validar configurações de autenticação

## 🔄 Atualizações Recentes

- ✅ Tratamento robusto de erros de rede
- ✅ Configuração automática de credenciais
- ✅ Teste de conectividade integrado
- ✅ Mensagens informativas em português
- ✅ Continuação do processo mesmo com falhas de rede
- ✅ **NOVO**: Normalização automática de caminhos UNC
- ✅ **NOVO**: Correção de interpretação de barras duplas
- ✅ **NOVO**: Compatibilidade entre diferentes sistemas

## 🔧 Correções Técnicas Implementadas

### Normalização de Caminhos UNC
```python
def normalize_unc_path(path_str: str) -> str:
    # Remove barras extras e normaliza
    path_str = path_str.replace("\\\\", "\\").replace("//", "/")
    
    # Garante que caminhos UNC tenham exatamente duas barras no início
    if path_str.startswith("\\"):
        if not path_str.startswith("\\\\"):
            path_str = "\\" + path_str
    
    return path_str
```

### Aplicação em Todos os Scripts
- `status_qlik_desktop.py`: Normalização antes de acessar pastas
- `status_qlik_etl.py`: Normalização antes de listar arquivos
- `network_config.py`: Normalização antes de testar conectividade
- `send_qlik_evolution.py`: Integração com configuração de rede
