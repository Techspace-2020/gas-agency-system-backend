from sqlalchemy import create_engine,event,text
from sqlalchemy.orm import sessionmaker, declarative_base
import os
from .config import settings
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")

engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True,pool_recycle=3600)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Connection event listeners for better error handling
@event.listens_for(engine, "connect")
def receive_connect(dbapi_conn, connection_record):
    logger.info("Database connection established")

@event.listens_for(engine, "checkout")
def receive_checkout(dbapi_conn, connection_record, connection_proxy):
    # Test connection before using
    cursor = dbapi_conn.cursor()
    try:
        cursor.execute("SELECT 1")
    except Exception as e:
        logger.error(f"Connection test failed: {e}")
        raise
    finally:
        cursor.close()