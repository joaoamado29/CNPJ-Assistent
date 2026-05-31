"""Comandos de barra (/ajuda, /status, ...) disponíveis no chat e nas pills.

Dois grupos:

- ``RESPOSTAS_COMANDOS``: comandos com resposta **hardcoded** (interceptados
  antes do LLM — instantâneos, sem custo).
- ``COMANDOS_LLM``: comandos que **viram prompts sintéticos** enviados ao
  agente IA. A LLM decide qual ferramenta chamar.

``COMANDOS_PILLS`` define a ordem de exibição na barra de pills.
"""

RESPOSTAS_COMANDOS = {
    # COMANDO AJUDA
    "/ajuda": """
    Qualquer mensagem com um CNPJ (14 dígitos) dispara a consulta automática.
    Você também pode pedir em linguagem natural ("pode olhar esse CNPJ pra mim?").

    **Comandos disponíveis:**
    - `/ajuda`: Mostra este texto.
    - `/status`: Mostra detalhes da sua última consulta.
    - `/historico`: Lista suas últimas 10 consultas.
    - `/resultado <id>`: Baixa a planilha de uma consulta anterior (ex.: `/resultado 4bea090e`).
    - `/limpar`: Apaga todo o histórico deste chat (não pode ser desfeito).""",
    # COMANDO LIMPAR (efeito colateral — tratado em webapp/chat.py)
    "/limpar": "Histórico apagado.",
}


COMANDOS_LLM = {
    "/historico": (
        "Liste minhas últimas 10 consultas. Use a ferramenta `listar_historico` "
        "com limite=10 e apresente em formato de lista numerada com: ID curto, "
        "status, quantos CNPJs e a data de criação. Se a lista vier vazia, "
        "informe que ainda não há consultas."
    ),
    "/status": (
        "Mostre detalhes da minha ÚLTIMA consulta. Use a ferramenta "
        "`listar_historico` com limite=1 e apresente: ID curto, status, "
        "quantos CNPJs foram processados e a data. Se não houver nenhuma "
        "consulta, informe que ainda não há histórico."
    ),
    "/resultado": (
        "O usuário digitou /resultado sem informar um ID. Use a ferramenta "
        "`listar_historico` com limite=5 para mostrar as últimas 5 consultas "
        "e instrua que ele deve enviar `/resultado <id>` (ou pedir em "
        "linguagem natural) para baixar a planilha desejada."
    ),
}


# Ordem fixa de exibição das pills no chat (mistura comandos diretos e via LLM).
COMANDOS_PILLS = ["/ajuda", "/status", "/historico", "/resultado", "/limpar"]


def resolver_comando(prompt: str) -> str | None:
    """Retorna a resposta hardcoded do comando, ou None se não for um comando direto.

    Comandos roteados pela LLM (`COMANDOS_LLM`) retornam None aqui — eles são
    tratados em `webapp/chat.computar_resposta`.
    """
    return RESPOSTAS_COMANDOS.get(prompt)