"""Worker da fila de consultas — processo separado, independente do navegador.

Roda fora do Streamlit (iniciado e supervisionado pelo ``docker/start.sh``).
Faz polling no banco por requests ``pending``, processa um de cada vez (a
automação é tela-única) e grava o resultado. Como não vive dentro de uma sessão
web, fechar o navegador no celular não interrompe o processamento.

Local (Windows, fora do Docker): rode em um terminal à parte com
``python worker.py``, apontando para o mesmo ``DATABASE_URL`` do app.
"""

from __future__ import annotations

import logging
import subprocess
import sys
import time

from webapp.consulta import processar_request
from webapp.db import repo

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [worker] %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("worker")

POLL_INTERVAL_SECONDS = 2.0


def _matar_chromes_orfaos() -> None:
    """No Linux/container, encerra Chromes que sobraram de uma queda anterior.

    A automação é tela-única: em repouso não deve haver nenhum Chrome aberto.
    Janelas órfãs confundem o casamento de imagens do pyautogui nas próximas
    consultas. Best-effort — ignora se não houver nada para matar.
    """
    if not sys.platform.startswith("linux"):
        return
    for alvo in ("chromium", "chrome"):
        try:
            subprocess.run(["pkill", "-f", alvo], check=False)
        except FileNotFoundError:
            pass


def _recuperar() -> None:
    """Recuperação de boot: destrava jobs órfãos e limpa a GUI antes de processar."""
    try:
        repo().reset_orphaned_processing()
    except Exception:
        logger.exception("Falha ao recuperar requests órfãos")
    _matar_chromes_orfaos()


def main() -> None:
    logger.info("Worker iniciado. Poll a cada %.1fs.", POLL_INTERVAL_SECONDS)
    _recuperar()
    r = repo()
    while True:
        try:
            req = r.claim_next_pending_request()
        except Exception:
            logger.exception("Erro ao reivindicar próximo request")
            time.sleep(POLL_INTERVAL_SECONDS)
            continue

        if req is None:
            time.sleep(POLL_INTERVAL_SECONDS)
            continue

        logger.info("Processando request %s (%d CNPJ[s])", req.id, req.total_cnpjs)
        try:
            processar_request(r, req.id)
            logger.info("Request %s finalizado", req.id)
        except Exception:
            logger.exception("Falha ao processar request %s; marcando failed", req.id)
            try:
                r.update_request_status(req.id, "failed")
            except Exception:
                logger.exception("Não consegui marcar %s como failed", req.id)


if __name__ == "__main__":
    main()
