"""Ponte entre a UI e a automação do Simples Nacional."""

from src.automation.simples_nacional import ConsultaResult, SimplesNacionalBot

from webapp.cnpj import formatar_cnpj


def consultar(cnpj: str) -> ConsultaResult:
    """Roda o bot para um CNPJ (14 dígitos) e garante o fechamento do Chrome."""
    bot = SimplesNacionalBot()
    try:
        return bot.consultar(formatar_cnpj(cnpj))
    finally:
        bot.close()


def formatar_resposta(r: ConsultaResult) -> str:
    """Monta o texto em markdown exibido no chat."""
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
