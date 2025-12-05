from sqlalchemy import Column, String, Text, Integer, JSON, ARRAY, ForeignKey, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid

from db.connexion_db import Base


class Dataset(Base):
    __tablename__ = "datasets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    qualified_name = Column(Text, unique=True, nullable=False)
    name = Column(Text, nullable=False)
    description = Column(Text)
    version_comment = Column(Text)
    signature = Column(JSON)
    columns_count = Column(Integer)
    columns_list = Column(ARRAY(Text))
    file_path = Column(Text)
    parent_qualified_name = Column(Text)

    owner_employee_id = Column(String(50),
                               ForeignKey("users.employee_id", onupdate="CASCADE", ondelete="RESTRICT"),
                               nullable=False)

    classification = Column(ARRAY(Text))
    created_at = Column(TIMESTAMP, server_default=func.now())
