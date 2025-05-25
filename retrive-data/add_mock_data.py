from db import SessionLocal
from models import ServiceProvider, TimeSlot
from datetime import datetime, time, date
import uuid

session = SessionLocal()

# Add a mock provider
provider = ServiceProvider(
    id=uuid.uuid4(),
    name="Dr.Patel",
    email="dr.patel@example.com",
    password_hash="hashedpassword",
    phone="1234567890",
    service_type="medical"
)
session.add(provider)
session.commit()

# Add a mock time slot for the provider
slot = TimeSlot(
    id=uuid.uuid4(),
    provider_id=provider.id,
    date=date(2025, 5, 26),
    time=time(10, 0),
    capacity=3,
    booked=1
)
session.add(slot)
session.commit()

session.close()