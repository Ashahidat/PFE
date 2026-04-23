from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from db.connexion_db import Base


class Glossary(Base):
    __tablename__ = "glossaries"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    qualified_name = Column(String(150), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    department = Column(String(50), nullable=True)
    created_by = Column(String(50), ForeignKey("users.employee_id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    categories = relationship("GlossaryCategory", back_populates="glossary", cascade="all, delete-orphan")
    terms = relationship("GlossaryTerm", back_populates="glossary", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Glossary(id={self.id}, name='{self.name}')>"


class GlossaryCategory(Base):
    __tablename__ = "glossary_categories"

    id = Column(Integer, primary_key=True, index=True)
    glossary_id = Column(Integer, ForeignKey("glossaries.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)
    qualified_name = Column(String(200), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    atlas_guid = Column(String(100), nullable=True)
    created_by = Column(String(50), ForeignKey("users.employee_id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    glossary = relationship("Glossary", back_populates="categories")
    terms = relationship("GlossaryTerm", back_populates="category", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<GlossaryCategory(id={self.id}, name='{self.name}', glossary_id={self.glossary_id})>"


class GlossaryTerm(Base):
    __tablename__ = "glossary_terms"

    id = Column(Integer, primary_key=True, index=True)
    glossary_id = Column(Integer, ForeignKey("glossaries.id", ondelete="CASCADE"), nullable=False)
    category_id = Column(Integer, ForeignKey("glossary_categories.id", ondelete="SET NULL"), nullable=True)
    term = Column(String(100), nullable=False)
    # Stable identifier used for Atlas qualifiedName. Must not change on rename.
    qualified_name = Column(String(200), unique=True, nullable=True)
    description = Column(Text, nullable=True)
    atlas_guid = Column(String(100), nullable=True)
    created_by = Column(String(50), ForeignKey("users.employee_id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    glossary = relationship("Glossary", back_populates="terms")
    category = relationship("GlossaryCategory", back_populates="terms")

    def __repr__(self):
        return f"<GlossaryTerm(id={self.id}, term='{self.term}', glossary_id={self.glossary_id}, category_id={self.category_id})>"
