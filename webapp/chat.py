"""Orquestração do chat: resolve a entrada e mantém o histórico de mensagens."""

import streamlit as st
import time

from webapp.cnpj import extrair_cnpj, formatar_cnpj
from webapp.comandos import resolver_comando
from webapp.consulta import consultar, formatar_resposta


def computar_resposta(prompt: str) -> str:
    """Resolve a resposta para a entrada: comando, consulta de CNPJ ou erro."""
    resposta = resolver_comando(prompt)
    if resposta is not None:
        return resposta

    cnpj = extrair_cnpj(prompt)
    if cnpj is None:
        return "Nenhum CNPJ encontrado na mensagem. Digite /ajuda para obter ajuda."

    with st.spinner(f"Consultando {formatar_cnpj(cnpj)}..."):
        return formatar_resposta(consultar(cnpj))


def registrar_pergunta(prompt: str) -> None:
    """Adiciona a mensagem do usuário e marca a resposta como pendente."""
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.session_state.resposta_pendente = prompt


def _digitar(texto: str):
    """Gera o texto palavra a palavra para simular o chat 'escrevendo'."""
    for palavra in texto.split(" "):
        yield palavra + " "
        time.sleep(0.03)


def responder_pendente(container) -> bool:
    """Responde a pergunta pendente com efeito de digitação. Retorna True se respondeu."""
    prompt = st.session_state.get("resposta_pendente")
    if not prompt:
        return False

    st.session_state.resposta_pendente = None
    resposta = computar_resposta(prompt)
    texto = container.chat_message("assistant").write_stream(_digitar(resposta))
    st.session_state.messages.append({"role": "assistant", "content": texto})
    return True


def on_pill() -> None:
    """Guarda o comando da pill e reseta a seleção (dispara só na mudança)."""
    st.session_state.comando_pendente = st.session_state.comando_pill
    st.session_state.comando_pill = None
