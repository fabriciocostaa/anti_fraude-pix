from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.orm import relationship
from models.base import Base


class PixTransaction(Base):
    __tablename__ = "pix_transaction"
    id = Column(BigInteger, primary_key=True)
    analysis_key = Column(UUID(as_uuid=True), unique=True, nullable=False)
    pix_id = Column(String(255), unique=True, nullable=False)
    status_id = Column(BigInteger, ForeignKey("pix_analysis_status.id"), nullable=False)
    amount = Column(BigInteger, nullable=False)
    transaction_date = Column(DateTime(timezone=True), nullable=False)
    received_at = Column(DateTime(timezone=True), nullable=False)
    evaluated_at = Column(DateTime(timezone=True), nullable=False)
    source_document = Column(String(14), nullable=False)
    source_branch = Column(Text, nullable=False)
    source_account_number = Column(Text, nullable=False)
    source_opening_date = Column(DateTime(timezone=True), nullable=False)
    destination_document = Column(String(14), nullable=False)
    destination_participant = Column(String(8), nullable=False)
    destination_branch = Column(Text, nullable=False)
    destination_account_number = Column(Text, nullable=False)
    destination_opening_date = Column(DateTime(timezone=True), nullable=False)
    device_id = Column(Text, nullable=False)
    channel = Column(Text, nullable=False)
    source_ip = Column(INET, nullable=False)
    latitude = Column(Numeric, nullable=True)
    longitude = Column(Numeric, nullable=True)
    declared_income = Column(String(100), nullable=True)
    income_consulted_at = Column(DateTime(timezone=True), nullable=True)
    raw_payload = Column(JSONB, nullable=False)
    decision_metadata = Column(JSONB, nullable=False)
    payload_hash = Column(String(64), nullable=False)
    policy_version = Column(String(100), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    status = relationship("PixAnalysisStatus")
    events = relationship("PixTransactionStatusEvent", back_populates="transaction")
