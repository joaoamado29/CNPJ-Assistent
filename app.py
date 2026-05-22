# Ponto de entrada do app Streamlit
import streamlit as st

from webapp.chat import on_pill, registrar_pergunta, responder_pendente
from webapp.comandos import RESPOSTAS_COMANDOS

def main() -> None:
    st.title("Consulta Simples Nacional")

    # Histórico persiste entre reruns
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Fonte única de renderização: todo o histórico é desenhado aqui
    messages = st.container(height="stretch")
    for msg in st.session_state.messages:
        messages.chat_message(msg["role"]).write(msg["content"])

    st.pills(
        "Comandos",
        list(RESPOSTAS_COMANDOS.keys()),
        key="comando_pill",
        on_change=on_pill,
    )

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

    # Mostra a pergunta e então responde com efeito de digitação (segundo rerun)
    responder_pendente(messages)


if __name__ == "__main__":
    main()
