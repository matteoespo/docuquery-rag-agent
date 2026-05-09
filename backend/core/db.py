'''
Initializes and connects the database
'''
from sqlalchemy.orm.session import Session
from sqlalchemy import create_engine
from core.models import Base
from sqlalchemy.orm import sessionmaker
from core.auth import get_user_by_username, create_user
from dotenv import load_dotenv
import os

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker[Session](autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Initializes the database by creating all tables defined in the models."""
    Base.metadata.create_all(bind=engine)

def ensure_admin_user():
    db = SessionLocal()
    try:
        if not get_user_by_username(db, "admin"):
            create_user(db, "admin", "admin")
            print("Admin user created: admin/admin")
        else:
            print("Admin user already exists.")
    finally:
        db.close()

