from sqlalchemy import Column, DateTime, Integer, String, UniqueConstraint, func
from models.base import Base


class PixAnalysisStatus(Base):
    __tablename__ = "pix_analysis_status"
    __table_args__ = (UniqueConstraint("enumerator"),)

    id = Column(Integer, primary_key=True)
    enumerator = Column(String(50), unique=True, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
