from sqlalchemy import BigInteger, Column, DateTime, String, func
from models.base import Base


class PixAnalysisStatus(Base):
    __tablename__ = "pix_analysis_status"
    id = Column(BigInteger, primary_key=True)
    enumerator = Column(String(50), unique=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
