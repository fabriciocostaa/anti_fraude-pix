from datetime import datetime
from uuid import uuid4
from sqlalchemy import text
from sqlalchemy.orm import joinedload
from models import PixAnalysisStatus, PixTransaction, PixTransactionStatusEvent


class PixTransactionRepository:
    def __init__(self, context):
        self.session = context.db_session

    def lock(self, identity):
        # Transacional, entre processos, inclusive quando ainda nao existe linha.
        self.session.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:identity, 0))"), {"identity": identity})

    def get_by_pix_id(self, pix_id):
        return self.session.query(PixTransaction).options(joinedload(PixTransaction.status)).filter_by(pix_id=pix_id).first()

    def get_cached_income(self, document):
        row = self.session.query(PixTransaction).filter(
            PixTransaction.source_document == document, PixTransaction.declared_income.isnot(None),
        ).order_by(PixTransaction.received_at.desc(), PixTransaction.id.desc()).first()
        return (row.declared_income, row.income_consulted_at) if row else None

    def get_history(self, document, since, as_of):
        rows = self.session.query(PixTransaction).options(joinedload(PixTransaction.status)).filter(
            PixTransaction.source_document == document,
            PixTransaction.received_at >= since, PixTransaction.received_at <= as_of,
        ).all()
        return [{
            "amount": row.amount, "status": row.status.enumerator,
            "received_at": row.received_at, "transaction_date": row.transaction_date,
            "destination_document": row.destination_document, "device_id": row.device_id,
            "source_branch": row.source_branch, "source_account_number": row.source_account_number,
        } for row in rows]

    def create(self, payload, raw_payload, payload_hash, status, metadata, received_at, evaluated_at, income, income_consulted_at):
        source, destination, origin = payload["source_account"], payload["destination_account"], payload["source"]
        geo = origin.get("geolocation", {})
        status_row = self.session.query(PixAnalysisStatus).filter_by(enumerator=status).one()
        transaction = PixTransaction(
            analysis_key=uuid4(), pix_id=payload["id"], status_id=status_row.id,
            amount=payload["amount"], transaction_date=datetime.fromisoformat(payload["transaction_date"]),
            received_at=received_at, evaluated_at=evaluated_at,
            source_document=source["owner"]["document_number"], source_branch=source["branch"],
            source_account_number=source["account_number"], source_opening_date=datetime.fromisoformat(source["opening_date"]),
            destination_document=destination["owner"]["document_number"], destination_participant=destination["participant"],
            destination_branch=destination["branch"], destination_account_number=destination["account_number"],
            destination_opening_date=datetime.fromisoformat(destination["opening_date"]),
            device_id=origin["device_id"], channel=origin["channel"], source_ip=origin["ip"],
            latitude=geo.get("latitude"), longitude=geo.get("longitude"),
            declared_income=income, income_consulted_at=income_consulted_at,
            raw_payload=raw_payload, payload_hash=payload_hash, policy_version=metadata["policy_version"],
            decision_metadata=metadata,
        )
        self.session.add(transaction)
        self.session.flush()
        self.session.add(PixTransactionStatusEvent(
            pix_transaction_id=transaction.id, status_id=status_row.id, event_datetime=evaluated_at,
        ))
        return transaction
