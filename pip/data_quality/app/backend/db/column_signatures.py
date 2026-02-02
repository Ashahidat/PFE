from sqlalchemy import Column, String, Float, BigInteger, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from db.connexion_db import Base
import uuid

class ColumnSignature(Base):
    __tablename__ = "column_signatures"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dataset_signature_id = Column(UUID(as_uuid=True), ForeignKey("dataset_signatures.id", ondelete="CASCADE"), nullable=False)
    column_name = Column(String, nullable=False)
    data_type = Column(String, nullable=False)
    mean = Column(Float, nullable=True)
    std = Column(Float, nullable=True)
    distinct_count = Column(BigInteger, nullable=True)
    sample_hash = Column(String, nullable=True)
