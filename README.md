# Consulta Simples Nacional

Consulta automática da situação de CNPJs no portal do **Simples Nacional** da Receita Federal.
Você manda um CNPJ (ou pede em linguagem natural) pela interface web, o sistema automatiza
a consulta no portal oficial, guarda o resultado em banco e permite exportar para planilha.

## Funcionalidades

- 💬 **Interface web (Streamlit)** — chat com efeito de digitação e comandos por *pills*.
- 🔐 **Login com Google (OIDC)** — autenticação nativa via `st.login`/`st.user` (Authlib).
- 🤖 **Agente IA conversacional (DeepSeek)** — entende linguagem natural ("pode olhar esse CNPJ pra mim?") via *tool calling*. Suporte a português direto.
- 📦 **Consulta em lote (até 100 CNPJs por mensagem)** — processados em ordem (FIFO), com barra de progresso e *status* no chat.
- 🆔 **ID em cada consulta** — cada lote ganha um ID curto (8 chars) para retomar depois com `/resultado <id>`.
- 🗂️ **Histórico por usuário** — chat e consultas salvos por e-mail logado e recarregados no login.
- 🔎 **Automação do portal** — consulta o [Portal do Simples Nacional](https://consopt.www8.receita.fazenda.gov.br/consultaoptantes) via PyAutoGUI (image matching).
- 🗄️ **Persistência** — PostgreSQL (padrão via docker-compose) ou SQLite local via SQLAlchemy.
- 📊 **Planilha xlsx** — para lotes de 2+ CNPJs, gerada em memória com botão de download no chat.

## Comandos de barra

| Comando | O que faz |
|---|---|
| `/ajuda` | Mostra a ajuda |
| `/historico` | Últimas consultas do usuário (também via "mostre meu histórico" pelo agente) |
| `/resultado <id>` | Rebaixa a planilha de uma consulta anterior |
| `/limpar` | Apaga todo o histórico de chat do usuário (irreversível) |

> Os comandos `/` são interceptados antes do LLM (atalho rápido, sem custo).
> Qualquer outra mensagem vai pelo agente DeepSeek.

## Stack

Python 3.11 · Streamlit · Authlib (login OIDC) · OpenAI SDK (cliente DeepSeek) · PyAutoGUI · SQLAlchemy · Pydantic Settings · openpyxl

## Estrutura

```
.
├── app.py                         # Ponto de entrada da interface web (login + chat)
├── requirements.txt
├── .env.example                   # Modelo de variáveis de ambiente
├── .streamlit/
│   └── secrets.toml.example       # Modelo de credenciais (OAuth Google + DeepSeek)
├── webapp/                        # Camada da UI web
│   ├── agente.py                  # Agente DeepSeek + tools (consultar_cnpjs, ...)
│   ├── contexto.md                # Contexto não-sensível injetado no system prompt
│   ├── chat.py                    # Orquestração do chat e roteamento
│   ├── comandos.py                # Comandos de barra (/Ajuda, /Limpar, ...)
│   ├── consulta.py                # Ponte UI ↔ automação + persistência
│   ├── historico.py               # Carrega/salva o histórico de chat por usuário
│   ├── cnpj.py                    # Extração e formatação de CNPJ
│   └── db.py                      # Plumbing compartilhado (sessão SQLAlchemy + Repository)
└── src/
    ├── config/settings.py         # Configuração via Pydantic Settings (.env)
    ├── core/                      # Validação de CNPJ e processamento em lote
    ├── automation/                # Automação do portal (browser bot via PyAutoGUI)
    ├── database/                  # Modelos, conexão e repositório
    └── export/                    # Geração de planilhas (xlsx)
```

## Como rodar

### 1. Pré-requisitos

- Python 3.11+
- Google Chrome instalado (a automação controla o navegador)
- Conta no Google Cloud (para o login OIDC)
- Conta no DeepSeek com saldo (para o agente IA)

### 2. Instalação

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows (PowerShell: .venv\Scripts\Activate.ps1)
# source .venv/bin/activate   # Linux/macOS

pip install -r requirements.txt
```

### 3. Configuração de ambiente

Copie o modelo de variáveis de ambiente e ajuste se necessário:

```bash
copy .env.example .env        # Windows
# cp .env.example .env        # Linux/macOS
```

Principais variáveis (veja `.env.example` para a lista completa):

| Variável | Descrição |
|---|---|
| `DATABASE_URL` | Conexão do banco (Postgres por padrão; SQLite local opcional) |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | Credenciais usadas pelo `docker-compose` ao provisionar o serviço `db` |
| `CHROME_HEADLESS` | Roda o Chrome sem interface gráfica |
| `MAX_WORKERS` | Instâncias paralelas do navegador |
| `REQUEST_DELAY_SECONDS` | Pausa entre consultas (rate limit) |

### 4. Login com Google (OIDC) e API DeepSeek

A interface exige login (OIDC nativo do Streamlit) **e** uma API key do DeepSeek
para o agente conversacional. Ambos vão em `.streamlit/secrets.toml`.

1. **Credencial OAuth Google** ([Cloud Console](https://console.cloud.google.com)):
   APIs e Serviços → **Clientes** → *ID do cliente OAuth* → tipo **Aplicativo da Web**.
   - Em **URIs de redirecionamento autorizados**, adicione exatamente:
     `http://localhost:8501/oauth2callback` (e a URL de produção, quando houver).
   - Copie `client_id` e `client_secret`.

2. **API key do DeepSeek** ([platform.deepseek.com](https://platform.deepseek.com)):
   - Cadastre-se e adicione saldo (US$ 2 dá pra muito teste).
   - **API keys → Create new API key** → copie (não dá pra ver depois).

3. **Crie o `secrets.toml`** a partir do modelo e preencha:

   ```bash
   copy .streamlit\secrets.toml.example .streamlit\secrets.toml   # Windows
   # cp .streamlit/secrets.toml.example .streamlit/secrets.toml   # Linux/macOS
   ```

   Gere o `cookie_secret` com:
   `python -c "import secrets; print(secrets.token_hex(32))"`

> Enquanto o app OAuth estiver em modo **Teste** no Google, só e-mails cadastrados
> em *Público-alvo → Usuários de teste* conseguem logar. O `secrets.toml` contém
> segredos e **não** é versionado (o `.gitignore` o exclui).

O histórico de cada usuário fica salvo na tabela `chat_messages` e é recarregado
no login, usando o mesmo banco do `DATABASE_URL`.

### 5. Customizar o agente

O contexto que o LLM recebe (limites, escopo, formato de resposta) está em
[webapp/contexto.md](webapp/contexto.md) — markdown puro, **não sensível**.
Edite à vontade e reinicie o Streamlit pra recarregar.

O agente usa `deepseek-chat` (V3) via API OpenAI-compatível. Modelo, base URL e
limites de round-trip ficam em `webapp/agente.py`.

### 6. Subir a interface web

```bash
streamlit run app.py
```

## Rodando com Docker

O `docker-compose` sobe **dois serviços**: o app (Chromium + Xvfb + Streamlit) e
um **PostgreSQL 16** (serviço `db`). O app conecta no Postgres por hostname `db`.

```bash
copy .env.example .env        # ajuste o .env antes (POSTGRES_PASSWORD etc.)
docker compose up --build
```

A interface fica em **http://localhost:8501** e o Postgres exposto em
**localhost:5432** (assim você consegue rodar o app **fora** do container
apontando pro mesmo banco, usando a `DATABASE_URL` postgres do `.env`).
As pastas `data/`, `data/postgres/`, `logs/` e `exports/` são montadas como
volume e persistem no host. O `.streamlit/` é montado **read-only** dentro do
container — segredos ficam só no host, nunca dentro da imagem.

> ⚠️ **Antes do primeiro `up`:** troque `POSTGRES_PASSWORD` no `.env` por uma
> senha forte. Gere com:
> `python -c "import secrets; print(secrets.token_urlsafe(32))"`

> **Rotação de keys (Google/DeepSeek):** edite o `.streamlit/secrets.toml` no
> host e rode `docker compose restart app`. Não precisa rebuild.

> **Nota sobre a automação:** o reconhecimento por imagem (`src/automation/images/*.png`)
> foi capturado no Chrome do Windows. A renderização no Chromium Linux é diferente,
> então pode ser necessário **recapturar essas imagens dentro do container** para a
> automação funcionar. A resolução da tela virtual (1920x1080) está definida em
> `docker/start.sh`.

## Configuração

Toda a configuração de runtime é lida do arquivo `.env` na raiz do projeto
através do `src/config/settings.py`. Os segredos da UI (OAuth Google + API key
DeepSeek) vivem em `.streamlit/secrets.toml`. **Nunca** versione esses dois
arquivos — ambos contêm segredos (o `.gitignore` e o `.dockerignore` já os
excluem). Use o `.env.example` e o `.streamlit/secrets.toml.example` como
referência.

## Aviso

Projeto para fins de automação de consultas em portal público. Respeite os termos de uso
do portal da Receita Federal e os limites de requisição (`REQUEST_DELAY_SECONDS`).