from sqlalchemy import Column, Integer, String, Text, Boolean
from db.connexion_db import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(String(50), unique=True, nullable=False)
    username = Column(String(100), nullable=False)
    password_hash = Column(Text, nullable=False)
    department = Column(String(100), nullable=False)
    role = Column(String(50), nullable=False, default="DATA_OWNER")
    is_protected = Column(Boolean, default=False) 
    is_active = Column(Boolean, default=True)