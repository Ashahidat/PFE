from sqlalchemy import Column, String, Text, ARRAY, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from db.connexion_db import Base

class Dataset(Base):
    __tablename__ = "datasets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(Text, nullable=False)
    file_path = Column(Text, nullable=False)
    hash = Column(Text, nullable=False)
    columns_list = Column(ARRAY(Text))
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())  # ajout timestamp
    owner_employee_id = Column(String(50), nullable=True)                     # ajout owner
    atlas_guid = Column(Text, nullable=True)                                  # ajout atlas_guid
