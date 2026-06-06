from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.database.connection import get_session
from src.database.models import CNPJQuery, ConsultaRequest

logger = logging.getLogger(__name__)


class Repository:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url

    def _session(self) -> Session:
        return get_session(self._database_url)

    # --- ConsultaRequest ---

    def create_request(
        self,
        user_email: str,
        cnpjs: list[str],
    ) -> ConsultaRequest:
        session = self._session()
        try:
            request = ConsultaRequest(
                user_email=user_email,
                total_cnpjs=len(cnpjs),
                status="pending",
            )
            session.add(request)
            session.flush()

            for cnpj in cnpjs:
                query = CNPJQuery(request_id=request.id, cnpj=cnpj, status="pending")
                session.add(query)

            session.commit()
            session.refresh(request)
            logger.info(
                "Request %s created with %d CNPJs for user %s",
                request.id,
                len(cnpjs),
                user_email,
            )
            return request
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get_request(self, request_id: str) -> ConsultaRequest | None:
        session = self._session()
        try:
            return session.query(ConsultaRequest).filter_by(id=request_id).first()
        finally:
            session.close()

    def get_requests_by_user(
        self, user_email: str, limit: int = 10
    ) -> list[ConsultaRequest]:
        """Most recent requests made by a given user, newest first."""
        session = self._session()
        try:
            rows = (
                session.query(ConsultaRequest)
                .filter_by(user_email=user_email)
                .order_by(ConsultaRequest.created_at.desc())
                .limit(limit)
                .all()
            )
            session.expunge_all()
            return rows
        finally:
            session.close()

    def get_request_by_prefix(
        self, prefix: str, user_email: str | None = None
    ) -> ConsultaRequest | None:
        """Find a request by the short 8-char id shown to users.

        When user_email is given, only matches requests owned by that user.
        """
        session = self._session()
        try:
            query = session.query(ConsultaRequest).filter(
                ConsultaRequest.id.like(f"{prefix}%")
            )
            if user_email is not None:
                query = query.filter_by(user_email=user_email)
            return query.first()
        finally:
            session.close()

    def update_request_status(
        self,
        request_id: str,
        status: str,
        *,
        error_message: str | None = None,
        processed_cnpjs: int | None = None,
    ) -> None:
        session = self._session()
        try:
            request = session.query(ConsultaRequest).filter_by(id=request_id).first()
            if not request:
                return
            request.status = status
            if error_message is not None:
                request.error_message = error_message
            if processed_cnpjs is not None:
                request.processed_cnpjs = processed_cnpjs
            if status in ("completed", "failed"):
                request.finished_at = datetime.now(timezone.utc)
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def claim_next_pending_request(self) -> ConsultaRequest | None:
        """Pega o request ``pending`` mais antigo e marca ``processing`` atomicamente.

        Em Postgres usa ``SELECT ... FOR UPDATE SKIP LOCKED`` para ser seguro
        mesmo se houver mais de um worker. Retorna o request (destacado da
        sessão) ou ``None`` se a fila estiver vazia.
        """
        session = self._session()
        try:
            query = (
                session.query(ConsultaRequest)
                .filter_by(status="pending")
                .order_by(ConsultaRequest.created_at.asc())
            )
            if session.bind.dialect.name.startswith("postgresql"):
                query = query.with_for_update(skip_locked=True)
            request = query.first()
            if request is None:
                return None
            request.status = "processing"
            session.commit()
            session.refresh(request)
            session.expunge(request)
            logger.info("Request %s reivindicado pelo worker", request.id)
            return request
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def reset_orphaned_processing(self) -> int:
        """Volta requests presos em ``processing`` para ``pending``.

        Recuperação de boot: se o worker morreu no meio de um job, o request
        ficou ``processing``. Voltando para ``pending``, ele é reivindicado de
        novo; como cada CNPJ guarda seu próprio status, só os ainda ``pending``
        são reprocessados (retoma de onde parou).
        """
        session = self._session()
        try:
            n = (
                session.query(ConsultaRequest)
                .filter_by(status="processing")
                .update(
                    {ConsultaRequest.status: "pending"}, synchronize_session=False
                )
            )
            session.commit()
            if n:
                logger.info("Recuperação: %d request(s) processing -> pending", n)
            return int(n)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    # --- CNPJQuery ---

    def get_pending_queries(self, request_id: str) -> list[CNPJQuery]:
        session = self._session()
        try:
            rows = (
                session.query(CNPJQuery)
                .filter_by(request_id=request_id, status="pending")
                .all()
            )
            session.expunge_all()
            return rows
        finally:
            session.close()

    def get_all_queries(self, request_id: str) -> list[CNPJQuery]:
        session = self._session()
        try:
            rows = (
                session.query(CNPJQuery).filter_by(request_id=request_id).all()
            )
            session.expunge_all()
            return rows
        finally:
            session.close()

    def update_query_result(
        self,
        query_id: str,
        *,
        status: str,
        nome_empresarial: str | None = None,
        situacao_simples: str | None = None,
        situacao_simei: str | None = None,
        periodos_anteriores_sn: str | None = None,
        periodos_anteriores_simei: str | None = None,
        eventos_futuros_sn: str | None = None,
        eventos_futuros_simei: str | None = None,
        mei_transportador_autonomo_cargas: str | None = None,
        raw_data: str | None = None,
        error_message: str | None = None,
    ) -> None:
        session = self._session()
        try:
            query = session.query(CNPJQuery).filter_by(id=query_id).first()
            if not query:
                return
            query.status = status
            query.attempts += 1
            query.consulted_at = datetime.now(timezone.utc)
            if nome_empresarial is not None:
                query.nome_empresarial = nome_empresarial
            if situacao_simples is not None:
                query.situacao_simples = situacao_simples
            if situacao_simei is not None:
                query.situacao_simei = situacao_simei
            if periodos_anteriores_sn is not None:
                query.periodos_anteriores_sn = periodos_anteriores_sn
            if periodos_anteriores_simei is not None:
                query.periodos_anteriores_simei = periodos_anteriores_simei
            if eventos_futuros_sn is not None:
                query.eventos_futuros_sn = eventos_futuros_sn
            if eventos_futuros_simei is not None:
                query.eventos_futuros_simei = eventos_futuros_simei
            if mei_transportador_autonomo_cargas is not None:
                query.mei_transportador_autonomo_cargas = mei_transportador_autonomo_cargas
            if raw_data is not None:
                query.raw_data = raw_data
            if error_message is not None:
                query.error_message = error_message
            if status in ("success", "error"):
                query.finished_at = datetime.now(timezone.utc)
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def increment_request_processed(self, request_id: str) -> int:
        session = self._session()
        try:
            request = session.query(ConsultaRequest).filter_by(id=request_id).first()
            if not request:
                return 0
            request.processed_cnpjs += 1
            session.commit()
            return request.processed_cnpjs
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
