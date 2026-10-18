from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from models.base import Base


class PixTransaction(Base):
    __tablename__ = "pix_transaction"
    __table_args__ = (
        UniqueConstraint("analysis_key"),
        UniqueConstraint("pix_id"),
    )

    id = Column(Integer, primary_key=True)
    analysis_key = Column(String(36), unique=True, nullable=False)
    pix_id = Column(String(255), unique=True, nullable=False)
    status_id = Column(Integer, ForeignKey("pix_analysis_status.id"), nullable=False)
    amount = Column(BigInteger, nullable=False)
    transaction_date = Column(DateTime(timezone=True), nullable=False)
    received_at = Column(DateTime(timezone=True), nullable=False)
    source_branch = Column(String(20), nullable=False)
    source_account_number = Column(String(50), nullable=False)
    source_document = Column(String(20), nullable=False)
    destination_document = Column(String(20), nullable=False)
    device_id = Column(String(255), nullable=False)
    declared_income = Column(String(100), nullable=True)
    income_consulted_at = Column(DateTime(timezone=True), nullable=True)
    payload_hash = Column(String(64), nullable=False)
    transaction_data = Column(JSONB, nullable=False)
    analysis_metadata = Column(JSONB, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    status = relationship("PixAnalysisStatus")
    events = relationship("PixTransactionStatusEvent", back_populates="transaction")
