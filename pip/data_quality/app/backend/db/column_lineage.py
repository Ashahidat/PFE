from sqlalchemy import Column, String, Text, TIMESTAMP, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from db.connexion_db import Base
import uuid

class ColumnLineage(Base):
    __tablename__ = "column_lineage"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    logical_column_id = Column(Text, nullable=False)
    column_name = Column(Text, nullable=False)
    dataset_version_id = Column(UUID(as_uuid=True), ForeignKey("dataset_versions.id"), nullable=False)
    parent_column_id = Column(UUID(as_uuid=True), ForeignKey("column_lineage.id"))
    data_type = Column(Text)
    created_at = Column(TIMESTAMP)

    dataset_version = relationship("DatasetVersion", backref="columns")
    parent_column = relationship("ColumnLineage", remote_side=[id])
