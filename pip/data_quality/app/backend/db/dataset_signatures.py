from sqlalchemy import Column, String, Integer, BigInteger, TIMESTAMP, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from db.connexion_db import Base
import uuid

class DatasetSignature(Base):
    __tablename__ = "dataset_signatures"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dataset_id = Column(UUID(as_uuid=True), ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False)
    structure_hash = Column(String, nullable=False)
    signature = Column(JSON, nullable=False)
    columns_count = Column(Integer, nullable=True)
    rows_count = Column(BigInteger, nullable=True)
    algo_version = Column(String, default="v1")
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
