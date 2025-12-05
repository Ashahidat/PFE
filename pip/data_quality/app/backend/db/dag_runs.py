from sqlalchemy import Column, String, ForeignKey, JSON, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from db.connexion_db import Base

class DAGRun(Base):
    __tablename__ = "dag_runs"

    id = Column(UUID(as_uuid=True), primary_key=True)
    dataset_id = Column(UUID(as_uuid=True), ForeignKey("datasets.id", ondelete="CASCADE"))
    dag_run_id = Column(String, nullable=False)
    rules = Column(JSON)
    status = Column(String, default="running")
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), onupdate=func.now())
