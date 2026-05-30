"""Ponte entre a UI e a automação do Simples Nacional."""

from __future__ import annotations

from typing import Callable

from src.automation.simples_nacional import ConsultaResult, SimplesNacionalBot

from webapp.cnpj import formatar_cnpj
from webapp.db import repo


def consultar(cnpj: str) -> ConsultaResult:
    """Roda o bot para um CNPJ (14 dígitos) e garante o fechamento do Chrome."""
    bot = SimplesNacionalBot()
    try:
        return bot.consultar(formatar_cnpj(cnpj))
    finally:
        bot.close()


def consultar_e_persistir(
    cnpjs: list[str],
    user_email: str,
    on_progress: Callable[[int, int, str], None] | None = None,
) -> tuple[str, list[ConsultaResult]]:
    """Cria ConsultaRequest, processa CNPJs em ordem (FIFO) e grava cada resultado.

    Retorna ``(request_id, lista de ConsultaResult na mesma ordem de cnpjs)``.
    Cada CNPJ vira uma linha em ``cnpj_queries`` e a consulta agregada em
    ``consulta_requests`` — buscável depois por ``/resultado <id>``.
    """
    r = repo()
    request = r.create_request(user_email=user_email, cnpjs=cnpjs)
    r.update_request_status(request.id, "processing")

    pending = r.get_pending_queries(request.id)
    q_by_cnpj = {q.cnpj: q for q in pending}

    resultados: list[ConsultaResult] = []
    sucessos = 0
    total = len(cnpjs)
    for i, cnpj in enumerate(cnpjs, start=1):
        if on_progress is not None:
            on_progress(i, total, cnpj)
        try:
            res = consultar(cnpj)
        except Exception as exc:
            res = ConsultaResult(cnpj=cnpj, success=False, error=str(exc))
        resultados.append(res)

        q = q_by_cnpj.get(cnpj)
        if q is not None:
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
            r.increment_request_processed(request.id)
        if res.success:
            sucessos += 1

    final_status = "completed" if sucessos > 0 else "failed"
    r.update_request_status(request.id, final_status)
    return request.id, resultados


def formatar_resposta(r: ConsultaResult) -> str:
    """Monta o texto em markdown exibido no chat para uma consulta única."""
    if not r.success:
        return f"Erro: {r.error or 'falha na consulta'}"
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