from sqlalchemy import Column, String, Text, TIMESTAMP, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from db.connexion_db import Base
import uuid

class ColumnDescription(Base):
    __tablename__ = "column_descriptions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dataset_version_id = Column(UUID(as_uuid=True), ForeignKey("dataset_versions.id", ondelete="CASCADE"), nullable=False)
    column_name = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    created_by = Column(String, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), onupdate=func.now())
    updated_by = Column(String, nullable=True)

    # Relations
    dataset_version = relationship("DatasetVersion", backref="column_descriptions")

    __table_args__ = (
        UniqueConstraint('dataset_version_id', 'column_name', name='uq_version_column'),
    )

    def __repr__(self):
        return f"<ColumnDescription {self.column_name} (version {self.dataset_version_id})>"