# db/classifications.py

import uuid
from sqlalchemy import Column, Text, Boolean, TIMESTAMP, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from db.connexion_db import Base


class EntityClassification(Base):
    __tablename__ = "entity_classifications"

    __table_args__ = (
        CheckConstraint(
            "entity_type IN ('DATASET', 'COLUMN')",
            name="ck_entity_type_valid"
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    entity_type = Column(Text, nullable=False)
    entity_id = Column(UUID(as_uuid=True), nullable=False)

    atlas_guid = Column(Text, nullable=False)

    # AJOUTEZ CE CHAMP MANQUANT :
    column_name = Column(Text, nullable=True)  # <-- MANQUANT !

    classification_name = Column(Text, nullable=False)
    classification_attributes = Column(JSONB)

    applied_by = Column(Text, nullable=False)
    department = Column(Text, nullable=False)
    business_unit = Column(Text, nullable=False)

    applied_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now()
    )

    is_active = Column(Boolean, default=True)