# 📚 Guia Completo do Git - WebScrapStatusQlik

## 🎯 Objetivo

Este guia fornece instruções completas para verificar, adicionar e gerenciar arquivos no seu repositório Git.

## 🔍 Como Verificar Arquivos Não Rastreados

### 1. Verificação Manual

#### Comando Básico
```bash
git status
```

#### Verificação Detalhada
```bash
# Arquivos não rastreados (não ignorados)
git ls-files --others --exclude-standard

# Arquivos ignorados
git ls-files --others --ignored --exclude-standard

# Status em formato compacto
git status --porcelain
```

### 2. Usando o Script Automatizado

Execute o script que criamos:
```bash
python verificar_git_status.py
```

Este script irá:
- ✅ Verificar o status geral do Git
- ✅ Listar arquivos não rastreados
- ✅ Mostrar arquivos ignorados
- ✅ Identificar arquivos modificados
- ✅ Verificar arquivos importantes
- ✅ Sugerir comandos para adicionar arquivos

## 📁 Arquivos que Devem Ser Rastreados

### Arquivos Essenciais do Projeto
- ✅ `requirements.txt` - Dependências Python
- ✅ `README.md` - Documentação principal
- ✅ `INSTALACAO.md` - Guia de instalação
- ✅ `SOLUCAO_ERRO_REDE.md` - Solução de problemas
- ✅ `RESUMO_ATUALIZACOES.md` - Resumo das mudanças
- ✅ `.env_exemple` - Exemplo de configuração

### Scripts Python
- ✅ `verificar_dependencias.py` - Verificação de dependências
- ✅ `verificar_git_status.py` - Verificação do Git
- ✅ `teste_caminhos_unc.py` - Teste de caminhos UNC
- ✅ `scheduler.py` - Agendador de tarefas
- ✅ `scheduler_config.py` - Configuração do scheduler

### Módulos do Projeto
- ✅ `crawler_qlik/` - Scripts de automação
- ✅ `evolution_api/` - Scripts de API
- ✅ `pysql/` - Scripts de banco de dados

## 🚫 Arquivos que Devem Ser Ignorados

### Configurados no .gitignore
- ❌ `.env` - Variáveis de ambiente (contém senhas)
- ❌ `.venv/` - Ambiente virtual Python
- ❌ `venv/` - Ambiente virtual alternativo
- ❌ `*.pdf` - Arquivos PDF (exceto documentação)
- ❌ `*.log` - Arquivos de log
- ❌ `*.txt` - Arquivos de texto (exceto documentação)
- ❌ `__pycache__/` - Cache Python
- ❌ `*.pyc` - Arquivos compilados Python

## 🔧 Comandos Úteis do Git

### Verificação de Status
```bash
# Status geral
git status

# Status compacto
git status --porcelain

# Verificar arquivos rastreados
git ls-files

# Verificar arquivos não rastreados
git ls-files --others --exclude-standard
```

### Adição de Arquivos
```bash
# Adicionar todos os arquivos
git add .

# Adicionar arquivo específico
git add nome_do_arquivo

# Adicionar múltiplos arquivos
git add arquivo1 arquivo2 arquivo3

# Adicionar arquivos por extensão
git add *.py
git add *.md
```

### Commit e Push
```bash
# Fazer commit
git commit -m "Descrição das mudanças"

# Verificar o que será commitado
git status

# Enviar para o repositório remoto
git push origin main

# Verificar histórico de commits
git log --oneline
```

## 🛠️ Solução de Problemas Comuns

### Problema: Arquivo não aparece no git status
**Solução:**
```bash
# Verificar se o arquivo está sendo ignorado
git check-ignore nome_do_arquivo

# Forçar adição de arquivo ignorado (use com cuidado)
git add -f nome_do_arquivo
```

### Problema: Arquivo foi adicionado por engano
**Solução:**
```bash
# Remover do staging area
git reset HEAD nome_do_arquivo

# Remover arquivo do repositório (mantém local)
git rm --cached nome_do_arquivo
```

### Problema: Quero ignorar um arquivo que já está rastreado
**Solução:**
```bash
# Remover do repositório (mantém local)
git rm --cached nome_do_arquivo

# Adicionar ao .gitignore
echo "nome_do_arquivo" >> .gitignore

# Fazer commit das mudanças
git add .gitignore
git commit -m "Adicionar arquivo ao .gitignore"
```

## 📋 Checklist de Verificação

### Antes de Fazer Commit
- [ ] Verificar se todos os arquivos importantes estão adicionados
- [ ] Verificar se arquivos sensíveis não estão sendo commitados
- [ ] Testar se o projeto ainda funciona
- [ ] Verificar se a documentação está atualizada

### Após Fazer Commit
- [ ] Verificar se o commit foi criado corretamente
- [ ] Verificar se o push foi realizado com sucesso
- [ ] Verificar se o repositório remoto está atualizado

## 🎯 Fluxo de Trabalho Recomendado

### 1. Desenvolvimento Diário
```bash
# 1. Verificar status
git status

# 2. Fazer alterações nos arquivos

# 3. Verificar o que mudou
git diff

# 4. Adicionar arquivos
git add .

# 5. Fazer commit
git commit -m "Descrição das mudanças"

# 6. Enviar para o repositório
git push origin main
```

### 2. Verificação Semanal
```bash
# 1. Executar script de verificação
python verificar_git_status.py

# 2. Verificar dependências
python verificar_dependencias.py

# 3. Verificar se há arquivos não rastreados importantes
git ls-files --others --exclude-standard
```

## 🔍 Scripts de Verificação

### verificar_git_status.py
Este script verifica automaticamente:
- Status geral do Git
- Arquivos não rastreados
- Arquivos ignorados
- Arquivos modificados
- Arquivos importantes do projeto

**Uso:**
```bash
python verificar_git_status.py
```

### verificar_dependencias.py
Este script verifica:
- Dependências Python instaladas
- Configuração do ChromeDriver
- Configuração do Oracle Client
- Arquivo .env
- Ambiente virtual

**Uso:**
```bash
python verificar_dependencias.py
```

## 📚 Recursos Adicionais

### Documentação do Git
- [Git Documentation](https://git-scm.com/doc)
- [GitHub Guides](https://guides.github.com/)
- [Git Cheat Sheet](https://education.github.com/git-cheat-sheet-education.pdf)

### Comandos Avançados
```bash
# Ver histórico detalhado
git log --graph --oneline --all

# Ver diferenças entre branches
git diff branch1..branch2

# Ver arquivos modificados em um commit
git show --name-only commit_hash

# Ver quem modificou um arquivo
git blame nome_do_arquivo
```

## 🎉 Dicas Importantes

1. **Sempre verifique o status antes de fazer commit**
2. **Use mensagens de commit descritivas**
3. **Mantenha o .gitignore atualizado**
4. **Faça commits pequenos e frequentes**
5. **Use os scripts de verificação regularmente**
6. **Mantenha a documentação atualizada**

---

**✅ Com este guia, você terá controle total sobre os arquivos do seu repositório Git!**
