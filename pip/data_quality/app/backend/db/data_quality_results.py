import uuid
from sqlalchemy import Column, String, Text, Integer, Boolean, TIMESTAMP, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB, DOUBLE_PRECISION
from sqlalchemy.sql import func
from db.connexion_db import Base

class DataQualityResult(Base):
    __tablename__ = "data_quality_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    dag_run_uuid = Column(UUID(as_uuid=True), ForeignKey("dag_runs.id", ondelete="CASCADE"), nullable=False)
    dataset_version_id = Column(UUID(as_uuid=True), ForeignKey("dataset_versions.id", ondelete="CASCADE"), nullable=False)

    validator_name = Column(Text, nullable=False)
    check_type = Column(Text, nullable=False)
    column_name = Column(Text, nullable=True)

    status = Column(Text, nullable=False)
    error_count = Column(Integer)
    ratio = Column(DOUBLE_PRECISION)
    alert = Column(Boolean)
    examples = Column(JSONB)

    created_at = Column(TIMESTAMP, server_default=func.now())
