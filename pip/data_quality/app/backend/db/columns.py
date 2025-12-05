from sqlalchemy import Column, String, Text, ForeignKey, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid

from db.connexion_db import Base


class DatasetColumn(Base):
    __tablename__ = "columns"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    dataset_id = Column(
        UUID(as_uuid=True),
        ForeignKey("datasets.id", ondelete="CASCADE"),
        nullable=False
    )

    name = Column(Text, nullable=False)
    qualified_name = Column(Text, nullable=False)
    data_type = Column(Text)
    created_at = Column(TIMESTAMP, server_default=func.now())
