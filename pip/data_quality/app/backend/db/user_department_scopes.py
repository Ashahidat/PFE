from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.sql import func

from db.connexion_db import Base


class UserDepartmentScope(Base):
    """
    Defines which departments a glossary admin is allowed to manage.
    """

    __tablename__ = "user_department_scopes"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(String(50), ForeignKey("users.employee_id", ondelete="CASCADE"), nullable=False)
    department_code = Column(String(100), ForeignKey("departments.code", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("employee_id", "department_code", name="uq_user_dept_scope"),
    )

    def __repr__(self):
        return f"<UserDepartmentScope(employee_id='{self.employee_id}', department_code='{self.department_code}')>"

