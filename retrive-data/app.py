from fastapi import FastAPI
from data_retrieval import get_provider_time_slots, get_providers, get_provider_by_name

app = FastAPI()

@app.get("/provider-time-slots/{provider_name}/{date}")
async def provider_time_slots(provider_name: str, date: str):
    return get_provider_time_slots(provider_name, date)

@app.get("/provider/{provider_name}")
async def get_provider(provider_name: str):
    return get_provider_by_name(provider_name)