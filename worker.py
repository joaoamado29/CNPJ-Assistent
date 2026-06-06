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
import os
import subprocess
import sys
import time
from pathlib import Path

from webapp.consulta import processar_request
from webapp.db import repo

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [worker] %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("worker")

POLL_INTERVAL_SECONDS = 2.0

# Expurgo agendado (limpeza de dados antigos). Tunável por variáveis de ambiente;
# os defaults abaixo já são: rodar a cada 24h, apagar o que passar de 24h, sem chat.
PURGE_INTERVAL_SECONDS = float(os.getenv("PURGE_INTERVAL_HOURS", "24")) * 3600
PURGE_RETENTION_HOURS = int(os.getenv("PURGE_RETENTION_HOURS", "24"))
PURGE_INCLUDE_CHAT = os.getenv("PURGE_INCLUDE_CHAT", "false").lower() in (
    "1",
    "true",
    "yes",
)
# Marcador persistido (data/ é volume montado) para o "a cada 24h" sobreviver a
# restarts/Stop-deallocate da VM — um timer só em memória zeraria a cada boot.
_LAST_PURGE_FILE = Path(__file__).parent / "data" / "last_purge.txt"


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


def _ler_ultimo_expurgo() -> float:
    """Epoch do último expurgo (marcador em data/, sobrevive a restart)."""
    try:
        return float(_LAST_PURGE_FILE.read_text().strip())
    except (FileNotFoundError, ValueError):
        return 0.0


def _registrar_expurgo(ts: float) -> None:
    try:
        _LAST_PURGE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _LAST_PURGE_FILE.write_text(str(ts))
    except OSError:
        logger.exception("Não consegui gravar o marcador de expurgo")


def _expurgar(r) -> None:
    """Apaga consultas (e opcionalmente chat) mais antigas que a retenção."""
    try:
        removidos = r.purge_older_than(
            PURGE_RETENTION_HOURS, include_chat=PURGE_INCLUDE_CHAT
        )
        logger.info(
            "Expurgo: %d registro(s) com mais de %dh removidos %s",
            sum(removidos.values()),
            PURGE_RETENTION_HOURS,
            removidos,
        )
    except Exception:
        logger.exception("Falha no expurgo")


def main() -> None:
    logger.info(
        "Worker iniciado. Poll %.1fs | expurgo a cada %.0fh (>%dh, chat=%s).",
        POLL_INTERVAL_SECONDS,
        PURGE_INTERVAL_SECONDS / 3600,
        PURGE_RETENTION_HOURS,
        PURGE_INCLUDE_CHAT,
    )
    _recuperar()
    r = repo()

    ultimo = _ler_ultimo_expurgo()
    if ultimo == 0.0:
        # 1ª vez: marca agora para o 1º expurgo só daqui a um intervalo — não
        # apaga dados pré-existentes logo no primeiro deploy.
        _registrar_expurgo(time.time())
        ultimo = time.time()
    proximo_expurgo = ultimo + PURGE_INTERVAL_SECONDS

    while True:
        if time.time() >= proximo_expurgo:
            _expurgar(r)
            _registrar_expurgo(time.time())
            proximo_expurgo = time.time() + PURGE_INTERVAL_SECONDS

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
