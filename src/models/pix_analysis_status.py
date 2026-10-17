from sqlalchemy import Column, Integer, String, DateTime, UniqueConstraint, func
from models.base import Base

class PixAnalysisStatus(Base):
    __tablename__ = 'pix_analysis_status'
    id = Column(Integer, primary_key=True, autoincrement=True)
    enumerator = Column(String(50), unique=True, nullable=False)