"""Comandos de barra (/Ajuda, /Status, ...) disponíveis no chat e nas pills."""

RESPOSTAS_COMANDOS = {
    # COMANDO AJUDA
    "/Ajuda": """
    Qualquer mensagem contendo um CNPJ (14 dígitos) dispara a consulta automática

    **Comandos disponíveis:**
    - `/Ajuda`: Mostra um texto de ajuda (este mesmo).
    - `/Status`: Status da ultima consulta.
    - `/Histórico`: Listar suas últimas consultas.
    - `/Resultado`: Baixar planilhas de uma consulta. Apontar o id da consulta desejada (ex: `/Resultado 4bea090e`).""",
    # COMANDO STATUS
    "/Status": "Texto de status aqui",
    # COMANDO HISTÓRICO
    "/Histórico": "Texto de histórico aqui",
    # COMANDO RESULTADO
    "/Resultado": "Texto de resultado aqui",
}


def resolver_comando(prompt: str) -> str | None:
    """Retorna a resposta do comando, ou None se não for um comando."""
    return RESPOSTAS_COMANDOS.get(prompt)
