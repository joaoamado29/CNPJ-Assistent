"""Orchestrates batch CNPJ processing with concurrency, retry, and progress tracking."""

from __future__ import annotations

import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Awaitable, Callable

from src.automation.simples_nacional import ConsultaResult, SimplesNacionalBot
from src.config.settings import Settings
from src.database.models import CNPJQuery
from src.database.repository import Repository

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[int, int, int, int], Awaitable[None]]


class BatchProcessor:
    """Processes a batch of CNPJs with bounded parallelism.

    Each worker runs a dedicated BotCity browser instance inside a thread.
    A semaphore limits the number of concurrent browser sessions.
    """

    def __init__(self, settings: Settings, repository: Repository) -> None:
        self._settings = settings
        self._repo = repository
        self._semaphore = asyncio.Semaphore(settings.max_workers)
        self._executor = ThreadPoolExecutor(
            max_workers=settings.max_workers,
            thread_name_prefix="botcity-worker",
        )

    async def process_request(
        self,
        request_id: str,
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        """Process all pending CNPJs for a request."""
        self._repo.update_request_status(request_id, "processing")
        queries = self._repo.get_pending_queries(request_id)

        if not queries:
            self._repo.update_request_status(request_id, "completed")
            return

        total = len(queries)
        counters = {"success": 0, "error": 0, "done": 0}
        lock = asyncio.Lock()

        async def _process_one(query):
            done = success = errors = 0
            try:
                async with self._semaphore:
                    loop = asyncio.get_running_loop()
                    logger.info("Processando CNPJ: %s", query.cnpj)
                    result = await loop.run_in_executor(
                        self._executor,
                        self._run_with_retry,
                        query.cnpj,
                    )
                    self._save_result(query.id, result)
                    logger.info("FINALIZADO: %s", query.cnpj)
                    async with lock:
                        if result.success:
                            counters["success"] += 1
                        else:
                            counters["error"] += 1
                        counters["done"] += 1
                        self._repo.increment_request_processed(request_id)
                        done, success, errors = (
                            counters["done"],
                            counters["success"],
                            counters["error"],
                        )
            except Exception as e:
                logger.exception("Erro ao processar CNPJ %s", query.cnpj)
                self._repo.update_query_result(
                    query.id,
                    status="error",
                    error_message=str(e),
                )
                async with lock:
                    counters["error"] += 1
                    counters["done"] += 1
                    self._repo.increment_request_processed(request_id)
                    done, success, errors = (
                        counters["done"],
                        counters["success"],
                        counters["error"],
                    )
            if progress_callback is not None:
                await progress_callback(done, total, success, errors)

        await asyncio.gather(*[_process_one(q) for q in queries])

        final_status = "completed" if counters["error"] < total else "failed"
        self._repo.update_request_status(request_id, final_status)
        logger.info(
            "Request %s finished: %d/%d success, %d errors",
            request_id,
            counters["success"],
            total,
            counters["error"],
        )

    def _run_with_retry(self, cnpj: str) -> ConsultaResult:
        """Execute a single CNPJ query with retry logic, managing browser lifecycle."""
        bot: SimplesNacionalBot | None = None
        last_result: ConsultaResult | None = None

        try:
            bot = SimplesNacionalBot()

            for attempt in range(1, self._settings.max_retries + 1):
                logger.info(
                    "Querying CNPJ %s (attempt %d/%d)",
                    cnpj,
                    attempt,
                    self._settings.max_retries,
                )
                last_result = bot.consultar(cnpj)

                if last_result.success:
                    return last_result

                logger.warning(
                    "Attempt %d failed for CNPJ %s: %s",
                    attempt,
                    cnpj,
                    last_result.error,
                )
                if attempt < self._settings.max_retries:
                    backoff = self._settings.request_delay_seconds * (2 ** (attempt - 1))
                    time.sleep(backoff)

            return last_result or ConsultaResult(
                cnpj=cnpj, success=False, error="All retry attempts exhausted."
            )

        except Exception as exc:
            logger.exception("Unhandled error processing CNPJ %s", cnpj)
            return ConsultaResult(cnpj=cnpj, success=False, error=str(exc))

        finally:
            if bot is not None:
                bot.close()

    def _save_result(self, query_id: str, result: ConsultaResult) -> None:
        self._repo.update_query_result(
            query_id,
            status="success" if result.success else "error",
            nome_empresarial=result.nome_empresarial,
            situacao_simples=result.situacao_simples,
            situacao_simei=result.situacao_simei,
            periodos_anteriores_sn=result.periodos_anteriores_sn,
            periodos_anteriores_simei=result.periodos_anteriores_simei,
            eventos_futuros_sn=result.eventos_futuros_sn,
            eventos_futuros_simei=result.eventos_futuros_simei,
            mei_transportador_autonomo_cargas=result.mei_transportador_autonomo_cargas,
            raw_data=result.raw_text,
            error_message=result.error,
        )

    def shutdown(self) -> None:
        self._executor.shutdown(wait=True, cancel_futures=False)
        logger.info("BatchProcessor executor shut down.")
