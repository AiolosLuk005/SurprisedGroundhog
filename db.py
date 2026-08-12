import datetime
from sqlalchemy import create_engine, Column, Integer, String, BigInteger, Text, DateTime, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.postgresql import ARRAY

from .config import DATABASE_URL

engine = create_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class FileORM(Base):
    __tablename__ = 'files'
    
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), nullable=False)
    filepath = Column(Text, unique=True, nullable=False, index=True)
    file_size = Column(BigInteger, nullable=False)
    file_type = Column(String(50), nullable=False)
    md5 = Column(String(32), nullable=False)
    
    # PostgreSQL 数组类型，用以表达多值标签
    ai_keywords = Column(ARRAY(String), default=list)
    scene = Column(ARRAY(String), default=list)
    category = Column(ARRAY(String), default=list)
    entity = Column(ARRAY(String), default=list)
    time_period = Column(ARRAY(String), default=list)
    
    ai_confidence = Column(Float, default=0.0)
    review_status = Column(Integer, default=0)  # 0=pending, 1=approved, 2=rejected
    
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

def init_db():
    Base.metadata.create_all(bind=engine)
