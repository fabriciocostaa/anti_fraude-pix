from datetime import datetime
from sqlalchemy import func

from database import Context
from models import PixTransaction, PixAnalysisStatus, PixTransactionStatusEvent

class PixTransactionRepository:

    def __init__(self, context: Context) -> None:
        self.session = context.db_session

    def create(self, analysis_key: str, payload: dict, status_enumerator: str, metadata: dict) -> PixTransaction:
        """
        Recebe os dados brutos e o resultado da análise para gravar no banco.
        Mapeia as propriedades aninhadas do payload de entrada para as colunas.
        """
        transaction = PixTransaction()

        transaction.analysis_key = analysis_key
        transaction.pix_id = payload["id"]
        transaction.amount = payload["amount"]
        transaction.transaction_date = datetime.fromisoformat(payload["transaction_date"])
        
        transaction.source_document = payload["source_account"]["owner"]["document_number"]
        transaction.destination_document = payload["destination_account"]["owner"]["document_number"]
        transaction.device_id = payload.get("source", {}).get("device_id")

        transaction.raw_payload = payload
        transaction.metadata_info = metadata 

        transaction.status = self.get_status(status_enumerator)

        self.session.add(transaction)
        return transaction

    def get_status(self, enumerator: str) -> PixAnalysisStatus:
        """Busca a referência do status (approved, rejected, two_factor_required)."""
        return self.session.query(PixAnalysisStatus).filter(PixAnalysisStatus.enumerator == enumerator).one()

    def get_by_pix_id(self, pix_id: str) -> PixTransaction:
        """
        Busca uma transação gravada pelo ID do Pix original (GET /pix/transaction/{id})[cite: 21, 33].
        """
        return self.session.query(PixTransaction).filter(PixTransaction.pix_id == pix_id).first()

    # ────────────────────────────────────────────────────────────────
    # QUERIES AUXILIARES PARA O MOTOR DE REGRAS ANTIFRAUDE
    # ────────────────────────────────────────────────────────────────

    def get_historical_amount_sum(self, document_number: str, since: datetime) -> int:
        """
        Calcula a soma de dinheiro transferida por um CPF/CNPJ a partir de uma data.
        Essencial para a regra de MONTANTE (Somou demais?)[cite: 15, 30].
        """
        result = self.session.query(func.sum(PixTransaction.amount)).filter(
            PixTransaction.source_document == document_number,
            PixTransaction.transaction_date >= since
        ).scalar()
        
        return result or 0

    def get_historical_transaction_count(self, document_number: str, since: datetime) -> int:
        """
        Conta quantas transferências o CPF/CNPJ fez a partir de uma data.
        Essencial para a regra de VELOCITY (Rápido demais?)[cite: 15, 30].
        """
        return self.session.query(PixTransaction).filter(
            PixTransaction.source_document == document_number,
            PixTransaction.transaction_date >= since
        ).count()