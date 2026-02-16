# db/models/data_quality_results.py
import sys
import os

PROJECT_ROOT = "/home/ashahi/PFE/pip/data_quality/app/backend"
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import uuid
from sqlalchemy import Column, String, Integer, Boolean, JSON, Float, TIMESTAMP, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from db.connexion_db import Base  

class DataQualityResult(Base):
    __tablename__ = "data_quality_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dag_run_uuid = Column(UUID(as_uuid=True), ForeignKey("dag_runs.id", ondelete="CASCADE"), nullable=False)
    dataset_version_id = Column(UUID(as_uuid=True), ForeignKey("dataset_versions.id", ondelete="CASCADE"), nullable=False)
    
    validator_name = Column(String, nullable=False)
    check_type = Column(String, nullable=False)
    column_name = Column(String)

    status = Column(String, nullable=False)
    error_count = Column(Integer)
    ratio = Column(Float)
    alert = Column(Boolean)
    examples = Column(JSON)

    created_at = Column(TIMESTAMP, server_default=func.now())
