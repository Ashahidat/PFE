from sqlalchemy import Column, String, Integer, Text, TIMESTAMP, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from db.connexion_db import Base
import uuid

class Process(Base):
    __tablename__ = "processes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    atlas_process_guid = Column(Text, unique=True, nullable=False)
    process_name = Column(Text, nullable=False)
    operation_type = Column(Text, nullable=False)
    input_dataset_version_id = Column(UUID(as_uuid=True), ForeignKey("dataset_versions.id"))
    output_dataset_version_id = Column(UUID(as_uuid=True), ForeignKey("dataset_versions.id"), nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())
    created_by = Column(String(50), ForeignKey("users.employee_id"))
    execution_time_ms = Column(Integer)
    status = Column(Text)
    process_metadata = Column("metadata", JSONB)

    input_version = relationship("DatasetVersion", foreign_keys=[input_dataset_version_id])
    output_version = relationship("DatasetVersion", foreign_keys=[output_dataset_version_id])