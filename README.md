# Consulta Simples Nacional

Consulta automática da situação de CNPJs no portal do **Simples Nacional** da Receita Federal.
Você manda um CNPJ pela interface web, o sistema automatiza a consulta no portal oficial,
guarda o resultado em banco e permite exportar para planilha.

## Funcionalidades

- 💬 **Interface web (Streamlit)** — chat com efeito de digitação e comandos por *pills*.
- 🔐 **Login com Google (OIDC)** — autenticação nativa via `st.login`/`st.user` (Authlib).
- 🗂️ **Histórico por usuário** — cada usuário logado tem seu chat salvo e recarregado no banco.
- 🔎 **Automação do portal** — consulta o [Portal do Simples Nacional](https://consopt.www8.receita.fazenda.gov.br/consultaoptantes) via Selenium/PyAutoGUI.
- 🗄️ **Persistência** — histórico de consultas em SQLite (padrão) ou PostgreSQL via SQLAlchemy.
- 📊 **Export** — geração de planilhas Excel (openpyxl) com os resultados.

## Stack

Python 3.11 · Streamlit · Authlib (login OIDC) · Selenium + PyAutoGUI · SQLAlchemy · Pydantic Settings · openpyxl

## Estrutura

```
.
├── app.py                      # Ponto de entrada da interface web (login + chat)
├── requirements.txt
├── .env.example                # Modelo de variáveis de ambiente
├── .streamlit/
│   └── secrets.toml.example    # Modelo de credenciais de login OIDC (Google)
├── webapp/                     # Camada da UI web
│   ├── chat.py                 # Orquestração do chat e efeito de digitação
│   ├── historico.py            # Carrega/salva o histórico de chat por usuário
│   ├── comandos.py             # Comandos de barra (/Ajuda, /Status, ...)
│   ├── consulta.py             # Ponte UI ↔ automação
│   └── cnpj.py                 # Extração e formatação de CNPJ
└── src/
    ├── config/settings.py      # Configuração via Pydantic Settings (.env)
    ├── core/                   # Validação de CNPJ e processamento em lote
    ├── automation/             # Automação do portal Simples Nacional (browser bot)
    ├── database/               # Modelos, conexão e repositório
    └── export/                 # Geração de planilhas
```

## Como rodar

### 1. Pré-requisitos

- Python 3.11+
- Google Chrome instalado (a automação controla o navegador)

### 2. Instalação

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows (PowerShell: .venv\Scripts\Activate.ps1)
# source .venv/bin/activate   # Linux/macOS

pip install -r requirements.txt
```

### 3. Configuração

Copie o modelo de variáveis de ambiente e ajuste se necessário:

```bash
copy .env.example .env        # Windows
# cp .env.example .env        # Linux/macOS
```

Principais variáveis (veja `.env.example` para a lista completa):

| Variável | Descrição |
|---|---|
| `DATABASE_URL` | Conexão do banco (SQLite por padrão) |
| `CHROME_HEADLESS` | Roda o Chrome sem interface gráfica |
| `MAX_WORKERS` | Instâncias paralelas do navegador |
| `REQUEST_DELAY_SECONDS` | Pausa entre consultas (rate limit) |

### 4. Login com Google (interface web)

A interface web exige login. A autenticação usa o OIDC nativo do Streamlit
(`st.login`/`st.user`, via Authlib) com o Google como provedor.

1. **Crie uma credencial OAuth** no [Google Cloud Console](https://console.cloud.google.com):
   APIs e Serviços → **Clientes** → *ID do cliente OAuth* → tipo **Aplicativo da Web**.
2. Em **URIs de redirecionamento autorizados**, adicione exatamente:
   `http://localhost:8501/oauth2callback` (e a URL de produção, quando houver).
3. Copie o `client_id` e o `client_secret`.
4. Crie o arquivo de segredos a partir do modelo e preencha os valores:

   ```bash
   copy .streamlit\secrets.toml.example .streamlit\secrets.toml   # Windows
   # cp .streamlit/secrets.toml.example .streamlit/secrets.toml   # Linux/macOS
   ```

   Gere o `cookie_secret` com:
   `python -c "import secrets; print(secrets.token_hex(32))"`

> Enquanto o app estiver em modo **Teste** no Google, só e-mails cadastrados em
> *Público-alvo → Usuários de teste* conseguem logar. O `secrets.toml` contém
> segredos e **não** é versionado (o `.gitignore` o exclui).

O histórico de cada usuário fica salvo na tabela `chat_messages` e é recarregado
no login, usando o mesmo banco do `DATABASE_URL`.

### 5. Interface web

```bash
streamlit run app.py
```

## Rodando com Docker

A imagem inclui Chromium + tela virtual (Xvfb) + window manager, então tanto a
interface web quanto a automação rodam dentro do container.

```bash
copy .env.example .env        # ajuste o .env antes (DATABASE_URL etc.)
docker compose up --build
```

A interface fica em **http://localhost:8501**. As pastas `data/`, `logs/` e
`exports/` são montadas como volume e persistem no host.

> **Nota sobre a automação:** o reconhecimento por imagem (`src/automation/images/*.png`)
> foi capturado no Chrome do Windows. A renderização no Chromium Linux é diferente,
> então pode ser necessário **recapturar essas imagens dentro do container** para a
> automação funcionar. A resolução da tela virtual (1920x1080) está definida em
> `docker/start.sh`.

## Configuração

Toda a configuração é lida do arquivo `.env` na raiz do projeto através do
`src/config/settings.py`. **Nunca** versione o `.env` nem o `.streamlit/secrets.toml`
— ambos contêm segredos (o `.gitignore` já os exclui). Use o `.env.example` e o
`.streamlit/secrets.toml.example` como referência.

## Aviso

Projeto para fins de automação de consultas em portal público. Respeite os termos de uso
do portal da Receita Federal e os limites de requisição (`REQUEST_DELAY_SECONDS`).