import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.orm import Session

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://pfe_user:12345@localhost:5432/pfe_db")

engine = create_engine(DATABASE_URL, echo=True)
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False
)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

print("📌 [DB] Connexion initialisée.")
