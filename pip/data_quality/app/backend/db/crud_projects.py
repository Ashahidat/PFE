from sqlalchemy.orm import Session
from db.projects import Project
import uuid

def create_project(db: Session, name: str, owner_employee_id: str, description: str = None):
    project = Project(
        id=uuid.uuid4(),
        name=name,
        description=description,
        owner_employee_id=owner_employee_id
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project

def get_user_projects(db: Session, owner_employee_id: str):
    return db.query(Project).filter(Project.owner_employee_id == owner_employee_id).all()

def get_project(db: Session, project_id: str):
    return db.query(Project).filter(Project.id == project_id).first()

def delete_project(db: Session, project_id: str):
    project = get_project(db, project_id)
    if project:
        db.delete(project)
        db.commit()
    return project