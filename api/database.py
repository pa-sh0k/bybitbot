from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import os

load_dotenv()

PG_USER     = os.getenv("PG_USER",     "postgres")
PG_PASSWORD = os.getenv("PG_PASSWORD", "")
PG_HOST     = os.getenv("PG_HOST",     "localhost")
PG_PORT     = os.getenv("PG_PORT",     "5432")
PG_DATABASE = os.getenv("PG_DATABASE", "postgres")

DATABASE_URL = (
    f"postgresql+psycopg2://{PG_USER}:{PG_PASSWORD}"
    f"@{PG_HOST}:{PG_PORT}/{PG_DATABASE}"
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()