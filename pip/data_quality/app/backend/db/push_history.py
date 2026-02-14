from sqlalchemy import Column, String, Integer, Text, TIMESTAMP, Boolean, Float, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from db.connexion_db import Base
import uuid

class PushHistory(Base):
    __tablename__ = "push_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dataset_id = Column(UUID(as_uuid=True), ForeignKey("datasets.id"), nullable=False)
    pushed_at = Column(TIMESTAMP)
    pushed_by = Column(String(50), ForeignKey("users.employee_id"))
    status = Column(Text)
    error_message = Column(Text)
    execution_time_ms = Column(Integer)
    columns_count = Column(Integer)
    rows_count = Column(Integer)
    parent_found = Column(Boolean)
    similarity_score = Column(Float)
    propagated_columns_count = Column(Integer)
