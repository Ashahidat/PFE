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
