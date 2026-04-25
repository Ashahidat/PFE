from sqlalchemy import Column, String, Boolean, DateTime
from sqlalchemy.sql import func

from db.connexion_db import Base


class Department(Base):
    __tablename__ = "departments"

    # Stable technical key (matches what we store on users/glossaries).
    code = Column(String(100), primary_key=True)
    label = Column(String(200), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    created_at = Column(DateTime, server_default=func.now())

    def __repr__(self):
        return f"<Department(code='{self.code}', label='{self.label}', active={self.is_active})>"

