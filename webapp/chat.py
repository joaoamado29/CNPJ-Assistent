"""Orquestração do chat: resolve a entrada e mantém o histórico de mensagens."""

from __future__ import annotations

import time
from dataclasses import dataclass

import streamlit as st

from src.export.spreadsheet import gerar_xlsx_bytes
from webapp.cnpj import MAX_CNPJS_POR_MENSAGEM, extrair_cnpjs, formatar_cnpj
from webapp.comandos import resolver_comando
from webapp.consulta import consultar_e_persistir, formatar_resposta
from webapp.db import repo
from webapp.historico import limpar_mensagens, salvar_mensagem


@dataclass
class Resposta:
    texto: str
    xlsx_bytes: bytes | None = None
    xlsx_filename: str | None = None


def computar_resposta(prompt: str) -> Resposta:
    """Resolve a resposta: /resultado, outros comandos, consulta (1 ou N) ou erro."""
    if prompt.startswith("/resultado"):
        user_email = st.session_state.get("user_id")
        if not user_email:
            return Resposta(texto="Faça login para usar /resultado.")
        return _resposta_resultado(prompt, user_email)

    cmd = resolver_comando(prompt)
    if cmd is not None:
        return Resposta(texto=cmd)

    todos = extrair_cnpjs(prompt, limite=MAX_CNPJS_POR_MENSAGEM + 1)
    if not todos:
        return Resposta(
            texto="Nenhum CNPJ encontrado na mensagem. Digite /ajuda para obter ajuda."
        )

    user_email = st.session_state.get("user_id")
    if not user_email:
        return Resposta(texto="Faça login para consultar CNPJs.")

    excedentes = max(0, len(todos) - MAX_CNPJS_POR_MENSAGEM)
    cnpjs = todos[:MAX_CNPJS_POR_MENSAGEM]

    if len(cnpjs) == 1:
        with st.spinner(f"Consultando {formatar_cnpj(cnpjs[0])}..."):
            request_id, resultados = consultar_e_persistir(cnpjs, user_email)
        texto = (
            formatar_resposta(resultados[0])
            + f"\n\n**Consulta ID:** `{request_id[:8]}`"
        )
        return Resposta(texto=texto)

    # 2+ CNPJs → barra de progresso + xlsx
    progresso = st.progress(0.0, text="Iniciando lote...")

    def _on_progress(i: int, total: int, cnpj_atual: str) -> None:
        progresso.progress(
            (i - 1) / total,
            text=f"Consultando {i}/{total} — {formatar_cnpj(cnpj_atual)}",
        )

    request_id, resultados = consultar_e_persistir(
        cnpjs, user_email, on_progress=_on_progress
    )
    progresso.progress(1.0, text="Concluído.")
    progresso.empty()

    queries = repo().get_all_queries(request_id)
    xlsx_bytes, xlsx_filename = gerar_xlsx_bytes(queries, request_id)

    sucessos = sum(1 for r in resultados if r.success)
    erros = len(resultados) - sucessos
    linhas = [
        f"**Lote concluído.** {len(resultados)} CNPJs — ✅ {sucessos} sucesso(s), ❌ {erros} erro(s).",
        f"**Consulta ID:** `{request_id[:8]}` — baixe novamente com `/resultado {request_id[:8]}`.",
        f"Planilha: `{xlsx_filename}`.",
    ]
    if excedentes:
        linhas.append(
            f"\n⚠️ Limite de {MAX_CNPJS_POR_MENSAGEM} CNPJs por mensagem — {excedentes} foram ignorados."
        )
    return Resposta(
        texto="\n\n".join(linhas),
        xlsx_bytes=xlsx_bytes,
        xlsx_filename=xlsx_filename,
    )


def _resposta_resultado(prompt: str, user_email: str) -> Resposta:
    """Recupera uma consulta anterior por ID e devolve o xlsx para download."""
    parts = prompt.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        return Resposta(
            texto="Uso: `/resultado <id>` (ex.: `/resultado 4bea090e`)."
        )
    prefixo = parts[1].strip().strip("`").strip()
    r = repo()
    req = r.get_request_by_prefix(prefixo, user_email=user_email)
    if not req:
        return Resposta(
            texto=f"Consulta `{prefixo}` não encontrada ou não pertence a você."
        )
    queries = r.get_all_queries(req.id)
    if not queries:
        return Resposta(texto=f"Consulta `{req.id[:8]}` está vazia.")
    xlsx_bytes, filename = gerar_xlsx_bytes(queries, req.id)
    criada_em = req.created_at.strftime("%d/%m/%Y %H:%M") if req.created_at else "—"
    texto = (
        f"**Consulta `{req.id[:8]}`** — {req.total_cnpjs} CNPJ(s), "
        f"status `{req.status}`, criada em {criada_em}."
    )
    return Resposta(texto=texto, xlsx_bytes=xlsx_bytes, xlsx_filename=filename)


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