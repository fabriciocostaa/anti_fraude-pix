from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from models.base import Base


class PixTransactionStatusEvent(Base):
    __tablename__ = "pix_transaction_status_event"
    id = Column(BigInteger, primary_key=True)
    pix_transaction_id = Column(BigInteger, ForeignKey("pix_transaction.id"), nullable=False)
    status_id = Column(BigInteger, ForeignKey("pix_analysis_status.id"), nullable=False)
    event_datetime = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    transaction = relationship("PixTransaction", back_populates="events")
