'''
Initializes and connects the database
'''
from sqlalchemy.orm.session import Session


import os
from sqlalchemy import create_engine
from models import Base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

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
