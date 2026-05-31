"""Orquestração do chat: resolve a entrada e mantém o histórico de mensagens."""

from __future__ import annotations

import time
from dataclasses import dataclass

import streamlit as st

from webapp.agente import conversar
from webapp.comandos import COMANDOS_LLM, resolver_comando
from webapp.historico import limpar_mensagens, salvar_mensagem


@dataclass
class Resposta:
    texto: str
    xlsx_bytes: bytes | None = None
    xlsx_filename: str | None = None


def computar_resposta(prompt: str) -> Resposta:
    """Roteia a entrada: comandos `/` → atalho; tudo o mais → agente IA."""
    cmd = resolver_comando(prompt)
    if cmd is not None:
        return Resposta(texto=cmd)

    user_email = st.session_state.get("user_id")
    if not user_email:
        return Resposta(texto="Faça login para conversar com o assistente.")

    # /historico e /status: comando vira prompt sintético antes de ir pro LLM.
    # Tudo o mais (CNPJ direto ou linguagem natural) passa cru.
    prompt_para_llm = COMANDOS_LLM.get(prompt, prompt)

    historico = st.session_state.get("messages", [])
    with st.spinner("Pensando..."):
        texto, xlsx_bytes, xlsx_filename = conversar(
            prompt_para_llm, user_email, historico
        )
    return Resposta(texto=texto, xlsx_bytes=xlsx_bytes, xlsx_filename=xlsx_filename)


def registrar_pergunta(prompt: str) -> None:
    """Adiciona a mensagem do usuário e marca a resposta como pendente.

    /limpar é tratado aqui (efeito colateral): apaga o histórico do usuário e
    não gera turno de chat — feedback vai por toast.
    """
    user_id = st.session_state.get("user_id")
    if prompt.strip() == "/limpar":
        if user_id:
            removidas = limpar_mensagens(user_id)
            st.toast(f"Histórico apagado ({removidas} mensagens).", icon="🧹")
        else:
            st.toast("Faça login antes de limpar o histórico.", icon="⚠️")
        st.session_state.messages = []
        return

    st.session_state.messages.append({"role": "user", "content": prompt})
    if user_id:
        salvar_mensagem(user_id, "user", prompt)
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

    chat_msg = container.chat_message("assistant")
    texto_renderizado = chat_msg.write_stream(_digitar(resposta.texto))
    if resposta.xlsx_bytes and resposta.xlsx_filename:
        chat_msg.download_button(
            label=f"📥 Baixar planilha ({resposta.xlsx_filename})",
            data=resposta.xlsx_bytes,
            file_name=resposta.xlsx_filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"dl_{resposta.xlsx_filename}",
        )

    st.session_state.messages.append({"role": "assistant", "content": texto_renderizado})
    if user_id := st.session_state.get("user_id"):
        salvar_mensagem(user_id, "assistant", texto_renderizado)
    return True


def on_pill() -> None:
    """Guarda o comando da pill e reseta a seleção (dispara só na mudança)."""
    st.session_state.comando_pendente = st.session_state.comando_pill
    st.session_state.comando_pill = None