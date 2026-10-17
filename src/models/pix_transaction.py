from sqlalchemy import Column, Integer, String, DateTime, JSON, ForeignKey
from src.models.base import Base # Ajuste a importação da sua Base consoante o repositório

class PixTransaction(Base):
    __tablename__ = 'pix_transaction'
    id = Column(Integer, primary_key=True, autoincrement=True)
    analysis_key = Column(String(36), unique=True, nullable=False)
    pix_id = Column(String(255), unique=True, nullable=False)
    status_id = Column(Integer, ForeignKey('pix_analysis_status.id'), nullable=False)
    
    amount = Column(Integer, nullable=False)
    transaction_date = Column(DateTime(timezone=True), nullable=False)
    source_document = Column(String(20), nullable=False)
    destination_document = Column(String(20), nullable=False)
    device_id = Column(String(255), nullable=True)
    
    raw_payload = Column(JSON, nullable=False)
    metadata = Column(JSON, nullable=True)