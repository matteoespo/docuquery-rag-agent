"""Authentication module for the backend using Kratos and SQLAlchemy"""

from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import bcrypt
import jwt
from datetime import datetime, timedelta
from core.models import User
from dotenv import load_dotenv
import os

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_user_by_id(db: Session, id: int) -> User | None:
    '''Get user by their id'''
    return db.query(User).filter(User.id == id).first()

def get_user_by_username(db: Session, username: str) -> User | None:
    '''Get a user by their username'''
    return db.query(User).filter(User.username == username).first()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    '''Verify a password by comparing it to a hashed password'''
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def authenticate_user(db: Session, username: str, password: str):
    '''Authenticate a user by their username and password'''
    user = get_user_by_username(db, username)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user

def hash_password(password: str) -> str:
    '''Hash a password using bcrypt'''
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def create_user(db: Session, username: str, password: str) -> User:
    '''Create a user'''
    if get_user_by_username(db, username):
        raise HTTPException(status_code=400, detail="Username already registered")

    hashed_password = hash_password(password)
    user = User(username=username, hashed_password=hashed_password)
    try:
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Username already registered")
    except Exception:
        db.rollback()
        raise

def delete_user(db: Session, user_id: int) -> bool:
    '''Delete a user by their id'''
    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    try:
        db.delete(user)
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise

def update_password(db: Session, user_id: int, old_password: str, new_password: str) -> User:
    '''Update a user's password'''
    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not verify_password(old_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect password")
    try:
        user.hashed_password = hash_password(new_password)
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise

def validate_password_strenght(password: str) -> bool:
    '''Validate the strength of a password'''
    if len(password) < 8:
        return False
    if not any(char.isupper() for char in password):
        return False
    if not any(char.islower() for char in password):
        return False
    if not any(char.isdigit() for char in password):
        return False
    if not any(char in "!@#$%^&*" for char in password):
        return False
    return True

def create_access_token(user_id: int) -> str:
    '''Create an access token for a user using jwt'''
    secret_key = os.getenv("SECRET_KEY")
    algorithm = os.getenv("JWT_ALGORITHM", "HS256")
    expiration_hours = int(os.getenv("JWT_EXPIRATION_HOURS", 24))
    
    payload = {
        "user_id": user_id,
        "exp": datetime.utcnow() + timedelta(hours=expiration_hours),
        "iat": datetime.utcnow()
    }
    
    token = jwt.encode(payload, secret_key, algorithm=algorithm)
    return token

def verify_token(token: str) -> dict | None:
    '''Verify and decode a JWT token'''
    try:
        secret_key = os.getenv("SECRET_KEY")
        algorithm = os.getenv("JWT_ALGORITHM", "HS256")
        payload = jwt.decode(token, secret_key, algorithms=[algorithm])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    

def revoke_token(token: str) -> bool:
    '''Revoke a token creating a blacklist of revoked tokens (not implemented)'''
    return True