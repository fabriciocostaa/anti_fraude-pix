from sqlalchemy import Column, Integer, String, DateTime, UniqueConstraint, func
from models.base import Base


class PixTransactionStatusEvent(Base):
    __tablename__ = 'pix_transaction_status_event'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    pix_transaction_id = Column(Integer, ForeignKey('pix_transaction.id'), nullable=False)
    status_id = Column(Integer, ForeignKey('pix_analysis_status.id'), nullable=False)
    event_datetime = Column(DateTime, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    transaction = relationship("PixTransaction", back_populates="events")