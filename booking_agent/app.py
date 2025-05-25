from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from datetime import datetime
from uuid import uuid4
from sqlalchemy import create_engine, Column, String, TIMESTAMP
from sqlalchemy.dialects.sqlite import BLOB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

app = FastAPI()

# SQLite for demo; replace with your DB URI as needed
DATABASE_URL = "sqlite:///c:/Users/nihar rakholiya/holbox/booking_agent/bookings.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
Base = declarative_base()
SessionLocal = sessionmaker(bind=engine)

class Book(Base):
    __tablename__ = "book"
    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    provider_name = Column(String, nullable=False)
    service_type = Column(String, nullable=False)
    date = Column(String, nullable=False)
    time_slot = Column(String, nullable=False)
    available_spots = Column(String, nullable=True)
    booking_reference = Column(String, nullable=False)
    status = Column(String, nullable=False, default="confirmed")
    booked_at = Column(TIMESTAMP, nullable=False, default=datetime.utcnow)

Base.metadata.create_all(bind=engine)

@app.post("/book")
async def book_slot(request: Request):
    data = await request.json()
    required_fields = ["provider_name", "service_type", "date", "time_slot", "booking_reference"]
    missing = [f for f in required_fields if not data.get(f)]
    if missing:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "message": f"Missing required fields: {', '.join(missing)}",
                "booking_reference": None
            }
        )

    db = SessionLocal()
    try:
        booking = Book(
            provider_name=data["provider_name"],
            service_type=data["service_type"],
            date=data["date"],
            time_slot=data["time_slot"],
            available_spots=str(data.get("available_spots")) if data.get("available_spots") is not None else None,
            booking_reference=data["booking_reference"],
            status="confirmed",
            booked_at=datetime.utcnow()
        )
        db.add(booking)
        db.commit()
        db.refresh(booking)
        return {
            "success": True,
            "message": f"Booking confirmed for {booking.provider_name} ({booking.service_type}) on {booking.date} at {booking.time_slot}.",
            "booking_reference": booking.booking_reference
        }
    except Exception as e:
        db.rollback()
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": f"Booking failed: {str(e)}",
                "booking_reference": None
            }
        )
    finally:
        db.close()