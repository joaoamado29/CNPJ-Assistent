# Agente Telegram – Simples Nacional

Consulta automática da situação de CNPJs no portal do **Simples Nacional** da Receita Federal.
O sistema recebe um CNPJ (por bot do Telegram ou pela interface web), automatiza a consulta no
portal oficial, guarda o resultado em banco e permite exportar para planilha.

## Funcionalidades

- 🤖 **Bot do Telegram** — envie um CNPJ e receba a situação do Simples Nacional / SIMEI.
- 💬 **Interface web (Streamlit)** — chat com efeito de digitação e comandos por *pills*.
- 🔎 **Automação do portal** — consulta o [Portal do Simples Nacional](https://consopt.www8.receita.fazenda.gov.br/consultaoptantes) via Selenium/PyAutoGUI.
- 🗄️ **Persistência** — histórico de consultas em SQLite (padrão) ou PostgreSQL via SQLAlchemy.
- 📊 **Export** — geração de planilhas Excel (openpyxl) com os resultados.

## Stack

Python 3.11 · Streamlit · python-telegram-bot · Selenium + PyAutoGUI · SQLAlchemy · Pydantic Settings · openpyxl

## Estrutura

```
.
├── app.py                      # Ponto de entrada da interface web (Streamlit)
├── requirements.txt
├── .env.example                # Modelo de variáveis de ambiente
├── webapp/                     # Camada da UI web
│   ├── chat.py                 # Orquestração do chat e efeito de digitação
│   ├── comandos.py             # Comandos de barra (/Ajuda, /Status, ...)
│   ├── consulta.py             # Ponte UI ↔ automação
│   └── cnpj.py                 # Extração e formatação de CNPJ
└── src/
    ├── config/settings.py      # Configuração via Pydantic Settings (.env)
    ├── core/                   # Validação de CNPJ e processamento em lote
    ├── automation/             # Bot de automação do portal Simples Nacional
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

Copie o modelo de variáveis de ambiente e preencha os valores:

```bash
copy .env.example .env        # Windows
# cp .env.example .env        # Linux/macOS
```

Principais variáveis (veja `.env.example` para a lista completa):

| Variável | Descrição |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Token do bot obtido com o [@BotFather](https://t.me/BotFather) |
| `TELEGRAM_ALLOWED_USERS` | IDs autorizados, separados por vírgula (vazio = todos) |
| `DATABASE_URL` | Conexão do banco (SQLite por padrão) |
| `CHROME_HEADLESS` | Roda o Chrome sem interface gráfica |

### 4. Interface web

```bash
streamlit run app.py
```

## Rodando com Docker

A imagem inclui Chromium + tela virtual (Xvfb) + window manager, então tanto a
interface web quanto a automação rodam dentro do container.

```bash
copy .env.example .env        # configure o .env antes (TELEGRAM_BOT_TOKEN etc.)
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
`src/config/settings.py`. **Nunca** versione o `.env` — ele contém segredos
(o `.gitignore` já o exclui). Use o `.env.example` como referência.

## Aviso

Projeto para fins de automação de consultas em portal público. Respeite os termos de uso
do portal da Receita Federal e os limites de requisição (`REQUEST_DELAY_SECONDS`).
