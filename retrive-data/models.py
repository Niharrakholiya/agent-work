from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, Date, Time, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
import uuid
from datetime import datetime
from db import engine

Base = declarative_base()

class ServiceProvider(Base):
    __tablename__ = 'service_providers'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    phone = Column(String(20))
    service_type = Column(String(50), nullable=False)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)

class TimeSlot(Base):
    __tablename__ = 'time_slots'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider_id = Column(UUID(as_uuid=True), ForeignKey('service_providers.id'))
    date = Column(Date, nullable=False)
    time = Column(Time, nullable=False)
    capacity = Column(Integer, nullable=False)
    booked = Column(Integer, default=0)
    provider = relationship("ServiceProvider")

Base.metadata.create_all(bind=engine)