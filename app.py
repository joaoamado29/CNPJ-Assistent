# Ponto de entrada do app Streamlit
import streamlit as st

from src.automation.simples_nacional import ConsultaResult
from src.export.spreadsheet import gerar_xlsx_bytes
from webapp.chat import on_pill, registrar_pergunta, responder_pendente
from webapp.comandos import COMANDOS_PILLS
from webapp.consulta import formatar_resposta
from webapp.db import repo
from webapp.historico import carregar_mensagens


def _query_para_result(q) -> ConsultaResult:
    """Mapeia uma linha de cnpj_queries para ConsultaResult (reusa formatar_resposta)."""
    return ConsultaResult(
        cnpj=q.cnpj,
        success=(q.status == "success"),
        nome_empresarial=q.nome_empresarial,
        situacao_simples=q.situacao_simples,
        situacao_simei=q.situacao_simei,
        periodos_anteriores_sn=q.periodos_anteriores_sn,
        periodos_anteriores_simei=q.periodos_anteriores_simei,
        eventos_futuros_sn=q.eventos_futuros_sn,
        eventos_futuros_simei=q.eventos_futuros_simei,
        mei_transportador_autonomo_cargas=q.mei_transportador_autonomo_cargas,
        error=q.error_message,
    )


@st.cache_data(show_spinner=False)
def _planilha_cacheada(request_id: str) -> tuple[bytes, str]:
    """Gera (uma vez por request) o xlsx do resultado, para um download estável."""
    return gerar_xlsx_bytes(repo().get_all_queries(request_id), request_id)


@st.fragment(run_every=2)
def painel_acompanhamento(user_email: str) -> None:
    """Acompanha a última consulta lendo do banco — sobrevive a fechar/reabrir o navegador.

    Enquanto ``pending``/``processing`` mostra o progresso; ao concluir mostra o
    resultado e, para lotes, o botão de download. Atualiza sozinho a cada 2s, sem
    depender do session_state (a fonte da verdade é o banco, alimentado pelo worker).
    """
    reqs = repo().get_requests_by_user(user_email, limit=1)
    if not reqs:
        return
    req = reqs[0]
    total = req.total_cnpjs or 0
    feito = req.processed_cnpjs or 0

    st.divider()
    st.caption(f"Última consulta · {req.id[:8]}")

    if req.status in ("pending", "processing"):
        rotulo = (
            "Na fila..." if req.status == "pending" else f"Consultando {feito}/{total}..."
        )
        st.progress((feito / total) if total else 0.0, text=rotulo)
        return

    queries = repo().get_all_queries(req.id)
    sucessos = sum(1 for q in queries if q.status == "success")
    erros = len(queries) - sucessos

    if len(queries) == 1:
        st.markdown(formatar_resposta(_query_para_result(queries[0])))
    else:
        icone = "✅" if req.status == "completed" else "⚠️"
        st.markdown(
            f"{icone} **Consulta {req.id[:8]}** — {sucessos} sucesso(s), {erros} erro(s)."
        )
        xlsx_bytes, filename = _planilha_cacheada(req.id)
        st.download_button(
            label=f"📥 Baixar planilha ({filename})",
            data=xlsx_bytes,
            file_name=filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"painel_dl_{req.id}",
        )


def main() -> None:
    st.title("Consulta Simples Nacional")

    # Exige login: sem usuário, mostra botão e para por aqui
    if not st.user.is_logged_in:
        st.info("Faça login para acessar suas consultas.")
        if st.button("Entrar com Google"):
            st.login()
        st.stop()

    user_id = st.user.email
    with st.sidebar:
        st.write(f"Logado como **{user_id}**")
        if st.button("Sair"):
            st.logout()

    # Carrega o histórico salvo do usuário uma vez por sessão
    if st.session_state.get("user_id") != user_id:
        st.session_state.user_id = user_id
        st.session_state.messages = carregar_mensagens(user_id)

    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Fonte única de renderização: todo o histórico é desenhado aqui
    messages = st.container(height="stretch")
    for msg in st.session_state.messages:
        messages.chat_message(msg["role"]).write(msg["content"])

    # Decide a entrada: chat tem prioridade, senão um comando pendente da pill
    prompt = None
    if chat_prompt := st.chat_input("Digite um CNPJ"):
        prompt = chat_prompt
    elif st.session_state.get("comando_pendente"):
        prompt = st.session_state.comando_pendente
        st.session_state.comando_pendente = None

    if prompt:
        registrar_pergunta(prompt)
        st.rerun()

    # Mostra a pergunta e então responde com efeito de digitação (segundo rerun).
    # Status da consulta (st.status do tool) aparece em ordem natural — entre o
    # histórico e as pills.
    responder_pendente(messages)

    # Acompanhamento da consulta (lê do banco, alimentado pelo worker em segundo
    # plano). Fica fora do fluxo do chat para sobreviver a fechar/reabrir o navegador.
    painel_acompanhamento(user_id)

    # Pills renderizadas POR ÚLTIMO → visualmente ficam logo acima do chat_input,
    # independente do que o agente desenhou durante a resposta.
    st.pills(
        "Comandos",
        COMANDOS_PILLS,
        key="comando_pill",
        on_change=on_pill,
    )


if __name__ == "__main__":
    main()
