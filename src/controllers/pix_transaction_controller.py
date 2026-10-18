from datetime import datetime, timedelta, timezone
from sqlalchemy.exc import IntegrityError
from controllers.base_controller import BaseController
from controllers.pix_rules import evaluate
from connectors.dict_connector import DictConnector
from connectors.serasa_connector import SerasaConnector
from dtos import PixTransactionDTO
from errors.pix_errors import DependencyUnavailable, PixConflict, PixNotFound
from repositories import PixTransactionRepository
from utils.pix_payload import normalize_payload


class PixTransactionController(BaseController):
    def __init__(self):
        super().__init__(__name__)
        self.repository = PixTransactionRepository(self.context)
        self.serasa_connector = SerasaConnector()
        self.dict_connector = DictConnector()

    def process_transaction(self, payload: dict) -> dict:
        normalized, fingerprint = normalize_payload(payload)
        document = normalized["source_account"]["owner"]["document_number"]
        receiver = normalized["destination_account"]["owner"]["document_number"]
        try:
            self.repository.lock("pix:" + normalized["id"])
            existing = self.repository.get_by_pix_id(normalized["id"])
            if existing:
                return self._replay(existing, fingerprint)

            self.repository.lock("payer:" + document)
            received_at = datetime.now(timezone.utc)
            cached_income = self.repository.get_cached_income(document)
            if cached_income:
                income, income_consulted_at = cached_income
                income_source = "stored"
            else:
                income = self.serasa_connector.get_income(document)
                income_consulted_at = datetime.now(timezone.utc) if income else None
                income_source = "serasa_mock" if income else "unavailable"

            dict_ok, marker = self.dict_connector.get_fraud_marker(receiver)
            if not dict_ok:
                raise DependencyUnavailable("dict_mock")
            dict_queried_at = datetime.now(timezone.utc)

            history = self.repository.get_history(document, received_at - timedelta(days=30), received_at)
            status, metadata = evaluate(normalized, history, income, marker, received_at)
            metadata["income"] = {
                "declared_income": income,
                "source": income_source,
                "consulted_at": income_consulted_at.isoformat() if income_consulted_at else None,
            }
            metadata["dict"] = {
                "source": "dict_mock",
                "simulated": True,
                "fraud_marker": marker,
                "queried_at": dict_queried_at.isoformat(),
            }
            metadata["simulated_enrichment"] = True
            evaluated_at = datetime.now(timezone.utc)

            transaction = self.repository.create(
                normalized,
                payload,
                fingerprint,
                status,
                metadata,
                received_at,
                evaluated_at,
                income,
                income_consulted_at,
            )
            result = PixTransactionDTO.to_dict(transaction)
            self.session.commit()
            return result
        except IntegrityError:
            self.session.rollback()
            existing = self.repository.get_by_pix_id(normalized["id"])
            if existing:
                return self._replay(existing, fingerprint)
            raise

    def _replay(self, transaction, fingerprint: str) -> dict:
        if transaction.payload_hash != fingerprint:
            raise PixConflict()
        result = PixTransactionDTO.to_dict(transaction)
        self.session.commit()
        return result

    def get_by_pix_id(self, pix_id: str) -> dict:
        transaction = self.repository.get_by_pix_id(pix_id)
        if transaction is None:
            raise PixNotFound()
        return PixTransactionDTO.to_dict(transaction)
