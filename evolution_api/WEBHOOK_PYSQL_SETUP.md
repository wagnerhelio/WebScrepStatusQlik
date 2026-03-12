# Webhook PySQL: disparar relatório por WhatsApp

O webhook permite acionar o relatório PySQL pelo WhatsApp. O bot pergunta: *"Deseja que execute o relatório? 1 para sim, 2 para não"*. **1** = executa e envia os arquivos para quem pediu; **2** = *"Tudo bem, obrigado!"*.

---

## 1. O que você precisa

- Evolution API rodando e instância conectada (WhatsApp).
- Arquivo `.env` na **raiz do projeto** com as variáveis da seção 2.
- Para registro **automático** do webhook: `requests` (já em `requirements.txt`).

---

## 2. Variáveis no `.env` (raiz do projeto)

Todas as variáveis abaixo devem estar no `.env` na pasta raiz (não dentro de `evolution_api/`).

| Variável | Obrigatória | Descrição | Exemplo |
|----------|-------------|-----------|---------|
| `EVOLUTION_BOT_NUMBER` | Sim (para responder) | Número do WhatsApp do robô, só dígitos | `5562995071258` |
| `WEBHOOK_PYSQL_PORT` | Não | Porta do servidor webhook | `5050` (padrão) |
| `WEBHOOK_PYSQL_ENABLED` | Não | Ativar webhook no scheduler | `true` (padrão) |
| `EVOLUTION_WEBHOOK_AUTO_REGISTER` | Não | Registrar webhook na Evolution ao iniciar o orquestrador | `true` ou `false` |
| `EVOLUTION_WEBHOOK_PUBLIC_URL` | Sim (se AUTO_REGISTER=true) | URL que a Evolution deve chamar (acessível pelo servidor Evolution) | `http://10.242.31.154:5050/webhook` |
| `EVOLUTION_BASE_URL` | Sim (para auto-register) | Base da Evolution API | `http://10.242.31.154:8080` |
| `EVOLUTION_API_TOKEN` | Sim (para auto-register) | Apikey da Evolution | (valor do header `apikey`) |
| `EVOLUTION_INSTANCE_NAME` | Sim (para auto-register) | Nome da instância | `bisspgo` |

**Opcionais:**

| Variável | Descrição | Padrão |
|----------|-----------|--------|
| `WEBHOOK_PYSQL_TIMEOUT_CONFIRMACAO` | Tempo em segundos para aguardar 1/2 | `300` (5 min) |
| `WEBHOOK_DEBUG` | Log extra no console ao receber mensagens | `false` |

**Exemplo de bloco no `.env`:**

```env
# Webhook PySQL
EVOLUTION_BOT_NUMBER=5562995071258
WEBHOOK_PYSQL_PORT=5050
WEBHOOK_PYSQL_ENABLED=true
EVOLUTION_WEBHOOK_AUTO_REGISTER=true
EVOLUTION_WEBHOOK_PUBLIC_URL=http://10.242.31.154:5050/webhook
```

Com `EVOLUTION_WEBHOOK_AUTO_REGISTER=true`, o script `iniciar_pysql_evolution.ps1` executa `evolution_api/registrar_webhook.py` antes do scheduler: ele verifica se a URL já está configurada na Evolution; se não estiver, registra. Assim o sistema sobe com o webhook já ativo, sem passo manual.

---

## 3. Registrar o webhook na Evolution API

A Evolution precisa saber qual URL chamar quando chegar uma mensagem (evento `MESSAGES_UPSERT`).

### 3.1 Automático (recomendado)

1. No `.env`: `EVOLUTION_WEBHOOK_AUTO_REGISTER=true` e `EVOLUTION_WEBHOOK_PUBLIC_URL=http://SEU_IP:5050/webhook` (use o IP/host da máquina onde o scheduler roda).
2. Inicie pelo orquestrador: `.\iniciar_pysql_evolution.ps1` ou `iniciar_pysql_evolution.bat`.
3. No passo **[4/5]** o script verifica/registra o webhook. Se já estiver correto, aparece *"Webhook já configurado na Evolution"*; caso contrário, *"Webhook registrado na Evolution com sucesso"*.

Não é necessário chamar a API da Evolution manualmente nesse caso.

### 3.2 Manual (uma vez ou se desativar o auto-register)

Se você não usar o auto-register ou quiser registrar/alterar manualmente, use a API da Evolution.

**PowerShell (formato que a Evolution v2 aceita):**

```powershell
$body = '{"webhook":{"enabled":true,"url":"http://SEU_IP:5050/webhook","events":["MESSAGES_UPSERT"],"webhookByEvents":false,"webhookBase64":false}}'
Invoke-RestMethod -Method Post -Uri "http://EVOLUTION_HOST:8080/webhook/set/SUA_INSTANCIA" -Headers @{ apikey = "SEU_EVOLUTION_API_TOKEN" } -ContentType "application/json" -Body $body
```

**Substitua:**

- `SEU_IP` → IP da máquina onde o scheduler/webhook rodam (ex.: `10.242.31.154`).
- `EVOLUTION_HOST` → host da Evolution API (ex.: `10.242.31.154` ou `localhost`).
- `SUA_INSTANCIA` → valor de `EVOLUTION_INSTANCE_NAME` (ex.: `bisspgo`).
- `SEU_EVOLUTION_API_TOKEN` → valor de `EVOLUTION_API_TOKEN`.

**Alternativa no .env da Evolution (global):** se você controla o container/serviço da Evolution, pode definir no `.env` dela: `WEBHOOK_GLOBAL_ENABLED=true`, `WEBHOOK_GLOBAL_URL=http://SEU_IP:5050/webhook`, `WEBHOOK_EVENTS_MESSAGES_UPSERT=true`.

---

## 4. Expor a URL (acessibilidade)

A Evolution precisa conseguir fazer HTTP POST na `EVOLUTION_WEBHOOK_PUBLIC_URL`.

- **Scheduler e Evolution na mesma máquina:** use `http://localhost:5050/webhook` ou `http://IP_DA_MAQUINA:5050/webhook`.
- **Scheduler e Evolution em máquinas diferentes na mesma rede:** use o IP da máquina do scheduler (ex.: `http://10.242.31.154:5050/webhook`). Garanta que a porta 5050 não esteja bloqueada por firewall.
- **Evolution em nuvem / internet:** exponha a porta 5050 com [ngrok](https://ngrok.com/) (ex.: `ngrok http 5050`) e use a URL HTTPS gerada em `EVOLUTION_WEBHOOK_PUBLIC_URL` (ex.: `https://xxxx.ngrok.io/webhook`).

---

## 5. Como rodar

- **Recomendado (tudo em um passo):** use o orquestrador. Ele faz: política de execução → venv → Docker (se aplicável) → **verificar/registrar webhook** → scheduler + webhook.
  ```powershell
  .\iniciar_pysql_evolution.ps1
  ```
  ou
  ```batch
  iniciar_pysql_evolution.bat
  ```

- **Só o scheduler (e webhook em thread):**
  ```bash
  python scheduler_pysql_evolution.py
  ```

- **Só o servidor webhook (teste):**
  ```bash
  python evolution_api/webhook_pysql.py
  ```

O servidor webhook escuta em `http://0.0.0.0:5050/webhook` (ou na porta definida em `WEBHOOK_PYSQL_PORT`).

---

## 6. Fluxo no WhatsApp

1. **No grupo:** escreva **relatório** ou **relatorio** (não precisa marcar o bot com @).  
   **No privado (conversa com o bot):** escreva **relatório**/relatorio ou qualquer mensagem.
2. O bot responde: *"Deseja que execute o relatório? 1 para sim, 2 para não"*.
3. **1** → o sistema executa o relatório PySQL e envia os arquivos também para quem pediu (grupo ou contato). **2** → o bot responde *"Tudo bem, obrigado!"*.
4. O estado “aguardando 1 ou 2” expira em 5 minutos (configurável com `WEBHOOK_PYSQL_TIMEOUT_CONFIRMACAO`).

O estado fica em `pysql/estado_webhook_pysql.json`.

---

## 7. Replicar em outra máquina

1. Copie o projeto e crie/ajuste o `.env` (pode usar `.env_exemple` como base).
2. No `.env` da **nova máquina**:
   - Ajuste `EVOLUTION_BASE_URL`, `EVOLUTION_API_TOKEN`, `EVOLUTION_INSTANCE_NAME` para a Evolution dessa rede.
   - Defina `EVOLUTION_WEBHOOK_PUBLIC_URL` com o **IP ou hostname dessa máquina** e a porta do webhook (ex.: `http://192.168.1.50:5050/webhook`).
   - Mantenha `EVOLUTION_WEBHOOK_AUTO_REGISTER=true`.
3. Execute uma vez: `iniciar_pysql_evolution.bat` ou `.\iniciar_pysql_evolution.ps1`.
4. O passo **[4/5]** registra (ou confirma) o webhook na Evolution; o **[5/5]** sobe o scheduler e o webhook. Não é necessário registrar o webhook manualmente na Evolution se o auto-register estiver ativo.

---

## 8. Troubleshooting

- **Bot não responde no WhatsApp**
  - Confirme que o scheduler está rodando e que aparece no console: *"Webhook PySQL: ativo"* e *"PySQL ouvindo em http://0.0.0.0:5050/webhook"*.
  - Ao enviar uma mensagem, deve aparecer no console: `[webhook] POST recebido event=messages.upsert`. Se não aparecer, a Evolution não está chamando a URL: verifique `EVOLUTION_WEBHOOK_PUBLIC_URL` e o registro na Evolution (passo 3).
  - Com `WEBHOOK_DEBUG=true` no `.env`, o console mostra mais detalhes das mensagens recebidas.

- **"instance requires property webhook"** ao registrar manualmente  
  Use o body com o objeto `webhook` (exemplo da seção 3.2).

- **Registro automático não faz nada**  
  Verifique se `EVOLUTION_WEBHOOK_AUTO_REGISTER=true`, `EVOLUTION_WEBHOOK_PUBLIC_URL`, `EVOLUTION_BASE_URL`, `EVOLUTION_API_TOKEN` e `EVOLUTION_INSTANCE_NAME` estão definidos no `.env` da raiz. O script `evolution_api/registrar_webhook.py` usa essas variáveis.
