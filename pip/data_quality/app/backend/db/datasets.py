from sqlalchemy import Column, String, DateTime, ForeignKey, ARRAY, Text
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from db.connexion_db import Base
import uuid


class Dataset(Base):
    __tablename__ = "datasets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    hash = Column(String, nullable=False)
    columns_list = Column(ARRAY(String), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    owner_employee_id = Column(String, nullable=True)
    atlas_guid = Column(String, nullable=True)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=True)
    description = Column(Text, nullable=True)  # ✅ NOUVEAU champ description
    
    # Relations
    project = relationship("Project", back_populates="datasets")