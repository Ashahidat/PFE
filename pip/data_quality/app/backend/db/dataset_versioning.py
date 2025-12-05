from sqlalchemy import Column, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from db.connexion_db import Base


class DatasetVersioning(Base):
    __tablename__ = "dataset_versioning"

    previous_id = Column(
        UUID(as_uuid=True),
        ForeignKey("datasets.id", ondelete="CASCADE"),
        primary_key=True
    )
    next_id = Column(
        UUID(as_uuid=True),
        ForeignKey("datasets.id", ondelete="CASCADE"),
        primary_key=True
    )
