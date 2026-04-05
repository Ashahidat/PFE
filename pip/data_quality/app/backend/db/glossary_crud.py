from sqlalchemy.orm import Session, joinedload
from db.glossary import Glossary, GlossaryTerm, GlossaryCategory
from typing import Optional, List


def get_all_glossaries(db: Session) -> List[Glossary]:
    """Liste tous les glossaires"""
    return db.query(Glossary).order_by(Glossary.name.asc()).all()


def get_all_glossaries_with_terms(db: Session) -> List[Glossary]:
    """Liste les glossaires avec leurs termes"""
    return db.query(Glossary).options(joinedload(Glossary.terms)).order_by(Glossary.name.asc()).all()


def get_glossaries_with_categories(db: Session) -> List[Glossary]:
    """Récupère les glossaires avec leurs catégories et termes associés"""
    return (
        db.query(Glossary)
        .options(
            joinedload(Glossary.categories)
            .joinedload(GlossaryCategory.terms)
            .joinedload(GlossaryTerm.category),
            joinedload(Glossary.terms).joinedload(GlossaryTerm.category),
        )
        .order_by(Glossary.name.asc())
        .all()
    )


def get_glossary_by_id(db: Session, glossary_id: int) -> Optional[Glossary]:
    return db.query(Glossary).filter(Glossary.id == glossary_id).first()


def create_glossary(
    db: Session,
    name: str,
    qualified_name: str,
    description: str,
    department: str,
    created_by: str
) -> Glossary:
    db_glossary = Glossary(
        name=name,
        qualified_name=qualified_name,
        description=description,
        department=department,
        created_by=created_by
    )
    db.add(db_glossary)
    db.commit()
    db.refresh(db_glossary)
    return db_glossary


def update_glossary(
    db: Session,
    glossary_id: int,
    name: str = None,
    qualified_name: str = None,
    description: str = None,
    department: str = None
) -> Optional[Glossary]:
    glossary = get_glossary_by_id(db, glossary_id)
    if not glossary:
        return None

    if name is not None:
        glossary.name = name
    if qualified_name is not None:
        glossary.qualified_name = qualified_name
    if description is not None:
        glossary.description = description
    if department is not None:
        glossary.department = department

    db.commit()
    db.refresh(glossary)
    return glossary


def delete_glossary(db: Session, glossary_id: int) -> bool:
    glossary = get_glossary_by_id(db, glossary_id)
    if not glossary:
        return False
    db.delete(glossary)
    db.commit()
    return True


def get_all_terms(db: Session) -> List[GlossaryTerm]:
    """Récupère tous les termes du glossaire"""
    return db.query(GlossaryTerm).options(joinedload(GlossaryTerm.category)).order_by(GlossaryTerm.term.asc()).all()


def get_term_by_id(db: Session, term_id: int) -> Optional[GlossaryTerm]:
    return db.query(GlossaryTerm).options(joinedload(GlossaryTerm.category)).filter(GlossaryTerm.id == term_id).first()


def get_all_categories(db: Session, glossary_id: int | None = None) -> List[GlossaryCategory]:
    query = db.query(GlossaryCategory)
    if glossary_id:
        query = query.filter(GlossaryCategory.glossary_id == glossary_id)
    return query.order_by(GlossaryCategory.name.asc()).all()


def get_category_by_id(db: Session, category_id: int) -> Optional[GlossaryCategory]:
    return db.query(GlossaryCategory).filter(GlossaryCategory.id == category_id).first()


def create_category(
    db: Session,
    glossary_id: int,
    name: str,
    qualified_name: str,
    description: str | None,
    created_by: str | None
) -> GlossaryCategory:
    category = GlossaryCategory(
        glossary_id=glossary_id,
        name=name,
        qualified_name=qualified_name,
        description=description,
        created_by=created_by
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


def update_category(
    db: Session,
    category_id: int,
    name: str | None = None,
    description: str | None = None,
    qualified_name: str | None = None
) -> Optional[GlossaryCategory]:
    category = get_category_by_id(db, category_id)
    if not category:
        return None
    if name is not None:
        category.name = name
    if description is not None:
        category.description = description
    if qualified_name is not None:
        category.qualified_name = qualified_name
    db.commit()
    db.refresh(category)
    return category


def delete_category(db: Session, category_id: int) -> bool:
    category = get_category_by_id(db, category_id)
    if not category:
        return False
    db.delete(category)
    db.commit()
    return True


def create_term(
    db: Session,
    glossary_id: int,
    category_id: int,
    term: str,
    description: str | None,
    created_by: str | None
) -> GlossaryTerm:
    """Crée un nouveau terme"""
    db_term = GlossaryTerm(
        glossary_id=glossary_id,
        category_id=category_id,
        term=term,
        description=description,
        created_by=created_by
    )
    db.add(db_term)
    db.commit()
    db.refresh(db_term)
    return db_term


def update_term(
    db: Session,
    term_id: int,
    term: str = None,
    description: str = None,
    category_id: int | None = None,
    glossary_id: int | None = None
) -> Optional[GlossaryTerm]:
    db_term = get_term_by_id(db, term_id)
    if not db_term:
        return None

    if glossary_id is not None:
        db_term.glossary_id = glossary_id
    if term is not None:
        db_term.term = term
    if description is not None:
        db_term.description = description
    if category_id is not None:
        db_term.category_id = category_id

    db.commit()
    db.refresh(db_term)
    return db_term


def delete_term(db: Session, term_id: int) -> bool:
    db_term = get_term_by_id(db, term_id)
    if not db_term:
        return False

    db.delete(db_term)
    db.commit()
    return True
