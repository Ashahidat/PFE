from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime
from sqlalchemy.sql import func
import sys
sys.path.append("/home/ashahi/PFE/pip/data_quality/app/backend")
from db.connexion_db import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(String(50), unique=True, nullable=False)
    username = Column(String(100), nullable=False)
    password_hash = Column(Text, nullable=False)
    department = Column(String(100), nullable=False)
    business_unit = Column(String(100), nullable=True)
    role = Column(String(20), nullable=False, default="DATA_OWNER")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_login = Column(DateTime(timezone=True), nullable=True)