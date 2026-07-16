import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

# 1. Load environment variables from .env
load_dotenv()

# 2. Get database connection URL
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")

if not SQLALCHEMY_DATABASE_URL:
    raise ValueError("DATABASE_URL is not set. Please check your .env file.")

# 3. Create SQLAlchemy engine
engine = create_engine(SQLALCHEMY_DATABASE_URL)

# 4. Create Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 5. Define Base class for SQLAlchemy 2.0 (This is what models.py is looking for!)
class Base(DeclarativeBase):
    pass

# 6. Database dependency for FastAPI routes
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()