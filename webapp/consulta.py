"""Ponte entre a UI e a automação do Simples Nacional."""

from __future__ import annotations

from src.automation.simples_nacional import ConsultaResult, SimplesNacionalBot
from src.database.repository import Repository

from webapp.cnpj import formatar_cnpj


def consultar(cnpj: str) -> ConsultaResult:
    """Roda o bot para um CNPJ (14 dígitos) e garante o fechamento do Chrome."""
    bot = SimplesNacionalBot()
    try:
        return bot.consultar(formatar_cnpj(cnpj))
    finally:
        bot.close()


def processar_request(r: Repository, request_id: str) -> None:
    """Processa os CNPJs ainda pendentes de um request já existente (usado pelo worker).

    Percorre apenas as queries ``pending``, então um request reaberto após uma
    queda retoma de onde parou — os CNPJs já concluídos são pulados. Cada CNPJ
    abre e fecha seu próprio Chrome via ``consultar()``. Ao final, define o
    status do request a partir de TODAS as queries: ``completed`` se houve ao
    menos um sucesso, senão ``failed``.
    """
    r.update_request_status(request_id, "processing")

    for q in r.get_pending_queries(request_id):
        try:
            res = consultar(q.cnpj)
        except Exception as exc:
            res = ConsultaResult(cnpj=q.cnpj, success=False, error=str(exc))
        r.update_query_result(
            q.id,
            status="success" if res.success else "error",
            nome_empresarial=res.nome_empresarial,
            situacao_simples=res.situacao_simples,
            situacao_simei=res.situacao_simei,
            periodos_anteriores_sn=res.periodos_anteriores_sn,
            periodos_anteriores_simei=res.periodos_anteriores_simei,
            eventos_futuros_sn=res.eventos_futuros_sn,
            eventos_futuros_simei=res.eventos_futuros_simei,
            mei_transportador_autonomo_cargas=res.mei_transportador_autonomo_cargas,
            raw_data=str(res.raw_text) if res.raw_text else None,
            error_message=res.error,
        )
        r.increment_request_processed(request_id)

    todas = r.get_all_queries(request_id)
    sucessos = sum(1 for q in todas if q.status == "success")
    r.update_request_status(request_id, "completed" if sucessos > 0 else "failed")


def formatar_resposta(r: ConsultaResult) -> str:
    """Monta o texto em markdown exibido no chat para uma consulta única."""
    if not r.success:
        return f"Erro na consulta do CNPJ {r.cnpj}: {r.error or 'falha na consulta'}"
    return (
        f"** Nome Empresárial: {r.nome_empresarial}**\n\n"
        f"- CNPJ: {r.cnpj}\n"
        f"- Situação Simples Nacional: {r.situacao_simples}\n"
        f"- Situação SIMEI: {r.situacao_simei}\n"
        f"- Períodos anteriores SN: {r.periodos_anteriores_sn}\n"
        f"- Períodos anteriores SIMEI: {r.periodos_anteriores_simei}\n"
        f"- Eventos futuros SN: {r.eventos_futuros_sn}\n"
        f"- Eventos futuros SIMEI: {r.eventos_futuros_simei}\n"
        f"- MEI Transportador Autônomo de Cargas: "
        f"{r.mei_transportador_autonomo_cargas}"
    )