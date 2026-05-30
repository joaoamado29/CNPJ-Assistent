"""Comandos de barra (/Ajuda, /Status, ...) disponíveis no chat e nas pills."""

RESPOSTAS_COMANDOS = {
    # COMANDO AJUDA
    "/ajuda": """
    Qualquer mensagem contendo um CNPJ (14 dígitos) dispara a consulta automática

    **Comandos disponíveis:**
    - `/ajuda`: Mostra um texto de ajuda (este mesmo).
    - `/status`: Status da ultima consulta.
    - `/histórico`: Listar suas últimas consultas.
    - `/resultado`: Baixar planilhas de uma consulta. Apontar o id da consulta desejada (ex: `/resultado 4bea090e`).
    - `/limpar`: Apaga todo o histórico deste chat (não pode ser desfeito).""",
    # COMANDO STATUS
    "/status": "Texto de status aqui",
    # COMANDO HISTÓRICO
    "/histórico": "Texto de histórico aqui",
    # COMANDO RESULTADO
    "/resultado": "Texto de resultado aqui",
    # COMANDO LIMPAR (efeito colateral — tratado em webapp/chat.py)
    "/limpar": "Histórico apagado.",
}


def resolver_comando(prompt: str) -> str | None:
    """Retorna a resposta do comando, ou None se não for um comando."""
    return RESPOSTAS_COMANDOS.get(prompt)
