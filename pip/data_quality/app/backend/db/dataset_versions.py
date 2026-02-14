from sqlalchemy import Column, String, Integer, Text, TIMESTAMP, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from db.connexion_db import Base
import uuid

class DatasetVersion(Base):
    __tablename__ = "dataset_versions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dataset_id = Column(UUID(as_uuid=True), ForeignKey("datasets.id"), nullable=False)
    version_number = Column(Integer, nullable=False)
    atlas_guid = Column(Text, nullable=False)
    parent_version_id = Column(UUID(as_uuid=True), ForeignKey("dataset_versions.id"))
    created_at = Column(TIMESTAMP)
    created_by = Column(String(50), ForeignKey("users.employee_id"))
    change_comment = Column(Text)
    source_file = Column(Text)

    dataset = relationship("Dataset", backref="versions")
    parent_version = relationship("DatasetVersion", remote_side=[id])
