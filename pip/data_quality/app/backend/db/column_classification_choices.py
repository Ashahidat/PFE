import uuid
from sqlalchemy import Column, String, Text, TIMESTAMP, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from db.connexion_db import Base


class ColumnClassificationChoice(Base):
    __tablename__ = "column_classification_choices"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dataset_version_id = Column(
        UUID(as_uuid=True),
        ForeignKey("dataset_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    column_name = Column(String, nullable=False)
    classification_name = Column(Text, nullable=False)  # 'PII' | 'SENSITIVE'

    created_by = Column(String, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), onupdate=func.now())
    updated_by = Column(String, nullable=True)

    dataset_version = relationship("DatasetVersion", backref="column_classification_choices")

    __table_args__ = (
        UniqueConstraint("dataset_version_id", "column_name", name="uq_version_column_classification_choice"),
    )

