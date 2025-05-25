from db import SessionLocal
from models import ServiceProvider, TimeSlot
from sqlalchemy.orm import Session
from sqlalchemy import func

def get_provider_time_slots(provider_name: str, date: str):
    session: Session = SessionLocal()
    try:
        # Use last name, case-insensitive, like in get_provider_by_name
        last_name = provider_name.strip().split()[-1].lower()
        provider = session.query(ServiceProvider).filter(
            func.lower(ServiceProvider.name).like(f"%{last_name}%")
        ).first()
        if not provider:
            return {"error": "Provider not found"}

        slots = session.query(TimeSlot).filter(TimeSlot.provider_id == provider.id, TimeSlot.date == date).all()
        available_slots = []

        for slot in slots:
            available_spots = slot.capacity - slot.booked
            available_slots.append({
                "time": slot.time.strftime('%H:%M'),
                "available_spots": available_spots,
                "total_capacity": slot.capacity
            })

        return {
            "provider": provider.name,
            "date": date,
            "available_slots": available_slots
        }
    finally:
        session.close()


def get_providers():
    session = SessionLocal()
    try:
        providers = session.query(ServiceProvider).all()
        return [
            {
                "id": str(provider.id),
                "name": provider.name,
                "email": provider.email,
                "phone": provider.phone,
                "service_type": provider.service_type
            }
            for provider in providers
        ]
    finally:
        session.close()


def get_provider_by_name(provider_name: str):
    session = SessionLocal()
    try:
        # Extract the last word (likely the last name)
        last_name = provider_name.strip().split()[-1].lower()
        # Find any provider whose name contains the last name (case-insensitive)
        provider = session.query(ServiceProvider).filter(
            func.lower(ServiceProvider.name).like(f"%{last_name}%")
        ).first()
        if not provider:
            return {"error": "Provider not found"}
        return {
            "id": str(provider.id),
            "name": provider.name,
            "email": provider.email,
            "phone": provider.phone,
            "service_type": provider.service_type
        }
    finally:
        session.close()