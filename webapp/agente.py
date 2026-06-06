"""Agente conversacional usando DeepSeek com tool calling.

DeepSeek expõe uma API OpenAI-compatível. Usamos o SDK ``openai`` com
``base_url`` apontando para ``https://api.deepseek.com``. O modelo
``deepseek-chat`` (V3) suporta function/tool calling.
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable

import streamlit as st
from openai import OpenAI

from src.export.spreadsheet import gerar_xlsx_bytes
from webapp.cnpj import MAX_CNPJS_POR_MENSAGEM, extrair_cnpjs
from webapp.db import repo

logger = logging.getLogger(__name__)

DEEPSEEK_MODEL = "deepseek-chat"
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
MAX_TOOL_ROUNDTRIPS = 5
MAX_HISTORICO_TURNS = 20  # turnos anteriores enviados ao modelo

SYSTEM_PROMPT_BASE = """Você é o assistente da plataforma "Consulta Simples Nacional".

Papel: ajudar o usuário a consultar a situação cadastral de CNPJs no portal do
Simples Nacional/SIMEI da Receita Federal, recuperar consultas anteriores e
baixar planilhas dos resultados.

Regras de ouro:
- Responda sempre em Português do Brasil. Tom direto, profissional, amigável.
- NUNCA invente situação cadastral, nome empresarial ou qualquer dado da
  Receita. Use SEMPRE as ferramentas para obter dados reais.
- Quando o usuário mencionar um ou mais CNPJs, extraia os 14 dígitos e chame
  `consultar_cnpjs` com a lista (só dígitos, sem pontuação).
- Não peça permissão para consultar quando o CNPJ já foi fornecido — execute.
- As consultas são ASSÍNCRONAS: `consultar_cnpjs` apenas ENFILEIRA e devolve um
  id; os dados NÃO voltam na chamada. Confirme que a consulta está processando e
  avise que o progresso e o resultado aparecem no painel "Última consulta" logo
  abaixo do chat. Nunca invente os dados.

As seções abaixo trazem o contexto operacional da plataforma. Siga-as como
fonte da verdade sobre limites, escopo e formato de resposta.
"""

_CONTEXTO_PATH = Path(__file__).parent / "contexto.md"


@lru_cache(maxsize=1)
def _carregar_contexto() -> str:
    """Lê webapp/contexto.md (cacheado por processo). Retorna string vazia se faltar."""
    try:
        return _CONTEXTO_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        logger.warning("contexto.md não encontrado em %s", _CONTEXTO_PATH)
        return ""


def _system_prompt() -> str:
    """SYSTEM_PROMPT final = base + contexto.md."""
    contexto = _carregar_contexto()
    if not contexto:
        return SYSTEM_PROMPT_BASE
    return f"{SYSTEM_PROMPT_BASE}\n\n---\n\n{contexto}"

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "consultar_cnpjs",
            "description": (
                "Enfileira a consulta de um ou mais CNPJs no portal do Simples Nacional. "
                "O processamento é ASSÍNCRONO: um worker processa em segundo plano (FIFO) "
                "e o progresso e o resultado aparecem no painel 'Última consulta' abaixo "
                "do chat. Retorna apenas {id, total_cnpjs, status:'enfileirada'} — NÃO "
                "retorna os dados do CNPJ. Avise o usuário que a consulta está processando."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "cnpjs": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Lista de CNPJs com 14 dígitos (só números, sem pontuação).",
                    }
                },
                "required": ["cnpjs"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "listar_historico",
            "description": "Lista as últimas consultas do usuário logado, decrescente.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limite": {
                        "type": "integer",
                        "description": "Quantas consultas trazer (padrão 10, máx 50).",
                        "default": 10,
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "baixar_resultado",
            "description": (
                "Recupera uma consulta anterior pelo ID (prefixo de 8 chars ou maior) "
                "e gera uma planilha xlsx que aparece como botão de download abaixo da resposta."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "consulta_id": {
                        "type": "string",
                        "description": "ID curto (8 chars) da consulta a recuperar.",
                    }
                },
                "required": ["consulta_id"],
            },
        },
    },
]


def _client() -> OpenAI:
    api_key = st.secrets["deepseek"]["api_key"]
    return OpenAI(api_key=api_key, base_url=DEEPSEEK_BASE_URL)


# ─── Implementação das tools ────────────────────────────────────────────────

def _tool_consultar_cnpjs(
    args: dict, user_email: str
) -> tuple[str, bytes | None, str | None]:
    cnpjs_in = args.get("cnpjs") or []
    raw = " ".join(str(c) for c in cnpjs_in)
    validos = extrair_cnpjs(raw, limite=MAX_CNPJS_POR_MENSAGEM)
    if not validos:
        return (json.dumps({"erro": "nenhum CNPJ válido na requisição"}), None, None)

    # Apenas enfileira (status "pending"); o worker em segundo plano processa.
    # Assim o trabalho não morre se o usuário fechar o navegador, e o progresso/
    # resultado são acompanhados pelo painel "Última consulta" (lê do banco).
    request = repo().create_request(user_email=user_email, cnpjs=validos)
    payload = {
        "id": request.id[:8],
        "total_cnpjs": len(validos),
        "status": "enfileirada",
    }
    return (json.dumps(payload, ensure_ascii=False), None, None)


def _tool_listar_historico(
    args: dict, user_email: str
) -> tuple[str, None, None]:
    try:
        limite = int(args.get("limite", 10))
    except (TypeError, ValueError):
        limite = 10
    limite = max(1, min(limite, 50))
    reqs = repo().get_requests_by_user(user_email, limit=limite)
    if not reqs:
        return (json.dumps({"consultas": []}), None, None)
    payload = [
        {
            "id": r.id[:8],
            "status": r.status,
            "total_cnpjs": r.total_cnpjs,
            "criada_em": r.created_at.strftime("%d/%m/%Y %H:%M") if r.created_at else None,
        }
        for r in reqs
    ]
    return (json.dumps({"consultas": payload}, ensure_ascii=False), None, None)


def _tool_baixar_resultado(
    args: dict, user_email: str
) -> tuple[str, bytes | None, str | None]:
    prefix = str(args.get("consulta_id", "")).strip().strip("`")
    if not prefix:
        return (json.dumps({"erro": "id_nao_informado"}), None, None)
    r = repo()
    req = r.get_request_by_prefix(prefix, user_email=user_email)
    if not req:
        return (
            json.dumps({"erro": f"consulta {prefix} não encontrada"}, ensure_ascii=False),
            None,
            None,
        )
    queries = r.get_all_queries(req.id)
    if not queries:
        return (
            json.dumps({"erro": f"consulta {req.id[:8]} vazia"}, ensure_ascii=False),
            None,
            None,
        )
    xlsx_bytes, filename = gerar_xlsx_bytes(queries, req.id)
    payload = {
        "id": req.id[:8],
        "total_cnpjs": req.total_cnpjs,
        "status": req.status,
        "criada_em": req.created_at.strftime("%d/%m/%Y %H:%M") if req.created_at else None,
        "planilha": filename,
    }
    return (json.dumps(payload, ensure_ascii=False), xlsx_bytes, filename)


_TOOL_REGISTRY: dict[
    str, Callable[[dict, str], tuple[str, bytes | None, str | None]]
] = {
    "consultar_cnpjs": _tool_consultar_cnpjs,
    "listar_historico": _tool_listar_historico,
    "baixar_resultado": _tool_baixar_resultado,
}


# ─── Loop principal ─────────────────────────────────────────────────────────

def conversar(
    prompt: str, user_email: str, historico: list[dict]
) -> tuple[str, bytes | None, str | None]:
    """Roda o loop de tool calling com DeepSeek.

    Devolve ``(resposta_final, xlsx_bytes, xlsx_filename)``. Os bytes/filename
    vêm da última tool que gerou planilha (se houver) e são renderizados como
    ``st.download_button`` no chat.
    """
    client = _client()

    messages: list[dict[str, Any]] = [{"role": "system", "content": _system_prompt()}]
    for msg in historico[-MAX_HISTORICO_TURNS:]:
        if msg.get("role") in ("user", "assistant") and msg.get("content"):
            messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": prompt})

    xlsx_bytes_final: bytes | None = None
    xlsx_filename_final: str | None = None

    for _ in range(MAX_TOOL_ROUNDTRIPS):
        resp = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
        )
        msg = resp.choices[0].message

        if not msg.tool_calls:
            return (msg.content or "", xlsx_bytes_final, xlsx_filename_final)

        messages.append(
            {
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in msg.tool_calls
                ],
            }
        )

        for tc in msg.tool_calls:
            name = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            handler = _TOOL_REGISTRY.get(name)
            if handler is None:
                tool_text = json.dumps({"erro": f"tool desconhecida: {name}"})
            else:
                try:
                    tool_text, x_bytes, x_name = handler(args, user_email)
                    if x_bytes is not None:
                        xlsx_bytes_final = x_bytes
                        xlsx_filename_final = x_name
                except Exception as exc:
                    logger.exception("Erro executando tool %s", name)
                    tool_text = json.dumps({"erro": str(exc)})
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": tool_text,
                }
            )

    return (
        "Limite de iterações de ferramentas atingido. Tente reformular a pergunta.",
        xlsx_bytes_final,
        xlsx_filename_final,
    )