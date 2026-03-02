# Evolution API – Docker

## Arquivo `.env`

O arquivo `.env` na pasta `evolution_api` já está configurado para rodar com o Docker Compose:

- **PostgreSQL**: usuário `evolution_user`, banco `evolution_db`, senha em `POSTGRES_PASSWORD`
- **Redis**: cache em `redis://redis:6379/6`
- **API**: porta `8080`, apikey em `AUTHENTICATION_API_KEY`

Para produção, altere no `.env`:

- `POSTGRES_PASSWORD` e a senha em `DATABASE_CONNECTION_URI`
- `AUTHENTICATION_API_KEY`

## Subir o ambiente

1. **Criar a rede** (só na primeira vez, se não usar Dokploy):

   ```bash
   docker network create dokploy-network
   ```

2. **Entrar na pasta e subir os containers**:

   ```bash
   cd evolution_api
   docker compose up -d
   ```

3. **Conferir se está rodando**:

   ```bash
   docker ps
   ```

   Você deve ver: `evolution_api`, `evolution_postgres`, `evolution_redis` com status **Up**.

## Conferir se a instalação funcionou

- **Logs da API**:
  ```bash
  docker logs evolution_api --tail 50
  ```
  Deve aparecer algo como: `HTTP - ON: 8080`, `Redis ready`, `Repository:Prisma - ON`.

- **Testar no navegador**: abra **http://localhost:8080**

- **Testar endpoint** (PowerShell, use a apikey do seu `.env`):
  ```powershell
  Invoke-RestMethod -Uri "http://localhost:8080/instance/fetchInstances" -Headers @{ apikey = "429683C4C977415CAAFCCE10F7D57E11" }
  ```
  Resposta vazia `[]` é normal quando ainda não há instâncias criadas.

## Parar e remover

```bash
cd evolution_api
docker compose down
```

Os volumes (dados do Postgres, Redis e instâncias) são mantidos. Para remover tudo, incluindo volumes:

```bash
docker compose down -v
```

## Imagem usada

O `docker-compose.yaml` usa a **imagem** `evoapicloud/evolution-api:latest`, que é a versão atualizada da Evolution API e evita o problema de **QR code não gerar** (a imagem antiga `atendai/evolution-api` na v2.2.3 tinha esse bug).

## QR code não aparece

Se o QR code ainda não aparecer ao conectar uma instância (Baileys):

1. **Atualize a versão do WhatsApp** no `.env`: abra o WhatsApp Web no navegador, vá em **Configurações (engrenagem) > Ajuda**. Lá aparece algo como "Versão 2.3000.XXXXXXXX". Use esse número em:
   ```env
   CONFIG_SESSION_PHONE_VERSION=2.3000.XXXXXXXX
   ```
2. Reinicie o container da API: `docker compose restart api`
3. Exclua a instância que não gerou QR (ex.: bisspgo) e crie de novo antes de pedir o QR novamente.
