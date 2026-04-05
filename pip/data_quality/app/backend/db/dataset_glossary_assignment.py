from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from db.connexion_db import Base
from db.glossary import GlossaryTerm


class DatasetGlossaryAssignment(Base):
    __tablename__ = "dataset_glossary_assignments"

    id = Column(Integer, primary_key=True, index=True)
    dataset_id = Column(ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False)
    glossary_term_id = Column(ForeignKey("glossary_terms.id", ondelete="CASCADE"), nullable=False)
    column_name = Column(String(150), nullable=True)
    created_by = Column(String(50), ForeignKey("users.employee_id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    dataset = relationship("Dataset", back_populates="glossary_assignments")
    term = relationship("GlossaryTerm")
