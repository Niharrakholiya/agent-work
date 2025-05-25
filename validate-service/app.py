from fastapi import FastAPI, Request, HTTPException
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pydantic import BaseModel
import httpx
from enum import Enum
import asyncio
import os

app = FastAPI()

# Configuration - Add your n8n API base URL here
N8N_API_BASE_URL = os.getenv("N8N_API_BASE_URL", "http://localhost:5678")

# Alternative: you can also hardcode it if you prefer
# N8N_API_BASE_URL = "http://localhost:5678"  # Change this to your n8n instance URL

# Data Models
class ValidationResult(str, Enum):
    VALID = "valid"
    VALID_WITH_ALTERNATIVE = "valid_with_alternative"
    INVALID_TIME_SLOT = "invalid_time_slot"
    INVALID_PROVIDER = "invalid_provider"
    INVALID_SERVICE = "invalid_service"
    MISSING_REQUIRED_DATA = "missing_required_data"
    PROVIDER_NOT_AVAILABLE = "provider_not_available"
    NO_CAPACITY = "no_capacity"

class IntentData(BaseModel):
    provider_name: Optional[str]
    time_slot: Optional[str]
    service_type: Optional[str]
    date: Optional[str]
    confidence: Optional[str] = "medium"

class ValidationResponse(BaseModel):
    is_valid: bool
    validation_result: ValidationResult
    error_message: Optional[str] = None
    suggestions: Optional[List[str]] = None
    validated_data: Optional[Dict[str, Any]] = None
    alternative_slots: Optional[List[Dict[str, Any]]] = None
    next_action: str  # "proceed_to_booking" or "return_error"

class IntentValidator:
    def __init__(self):
        self.required_fields = ["provider_name", "service_type", "date", "time_slot"]

    async def validate_intent(self, intent_data: IntentData) -> ValidationResponse:
        """Main validation logic with capacity management and auto-suggestion"""

        # Step 1: Check for missing required data
        missing_fields = self._check_missing_fields(intent_data)
        if missing_fields:
            return ValidationResponse(
                is_valid=False,
                validation_result=ValidationResult.MISSING_REQUIRED_DATA,
                error_message=f"Missing required information: {', '.join(missing_fields)}",
                suggestions=self._generate_missing_field_suggestions(missing_fields),
                next_action="return_error"
            )

        # Step 2: Validate service type and provider match
        provider_validation = await self._validate_provider(intent_data.provider_name, intent_data.service_type)
        if not provider_validation["valid"]:
            return ValidationResponse(
                is_valid=False,
                validation_result=ValidationResult.INVALID_PROVIDER,
                error_message=provider_validation["message"],
                suggestions=provider_validation["suggestions"],
                next_action="return_error"
            )

        # Step 3: Enhanced time slot validation with capacity check
        time_validation = await self._validate_time_slot_with_capacity(
            intent_data.date, 
            intent_data.time_slot, 
            intent_data.provider_name
        )
        
        if time_validation["status"] == "exact_match":
            # Perfect match - requested slot is available
            return ValidationResponse(
                is_valid=True,
                validation_result=ValidationResult.VALID,
                validated_data={
                    "provider_name": intent_data.provider_name,
                    "service_type": intent_data.service_type,
                    "date": intent_data.date,
                    "time_slot": time_validation["confirmed_slot"]["time"],
                    "available_spots": time_validation["confirmed_slot"]["available_spots"],
                    "booking_reference": f"REF_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                },
                next_action="proceed_to_booking"
            )
        
        elif time_validation["status"] == "alternative_found":
            # Original slot not available, but alternatives suggested
            return ValidationResponse(
                is_valid=True,
                validation_result=ValidationResult.VALID_WITH_ALTERNATIVE,
                error_message=time_validation["message"],
                validated_data={
                    "provider_name": intent_data.provider_name,
                    "service_type": intent_data.service_type,
                    "date": intent_data.date,
                    "time_slot": time_validation["suggested_slot"]["time"],
                    "available_spots": time_validation["suggested_slot"]["available_spots"],
                    "booking_reference": f"REF_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                },
                alternative_slots=time_validation["alternatives"],
                suggestions=[
                    f"Your preferred time {intent_data.time_slot} is not available.",
                    f"I've found the nearest available slot: {time_validation['suggested_slot']['time']}",
                    "You can also choose from other available times listed below."
                ],
                next_action="proceed_to_booking"
            )
        
        else:
            # No slots available
            return ValidationResponse(
                is_valid=False,
                validation_result=ValidationResult.NO_CAPACITY,
                error_message=time_validation["message"],
                suggestions=time_validation["suggestions"],
                alternative_slots=time_validation.get("alternatives", []),
                next_action="return_error"
            )

    def _check_missing_fields(self, intent_data: IntentData) -> List[str]:
        """Check for missing required fields"""
        missing = []
        for field in self.required_fields:
            value = getattr(intent_data, field)
            if not value or value.strip() == "":
                missing.append(field)
        return missing

    def _generate_missing_field_suggestions(self, missing_fields: List[str]) -> List[str]:
        """Generate helpful suggestions for missing fields"""
        suggestions = []
        field_prompts = {
            "provider_name": "Please specify which doctor, salon, or service provider you'd like to book with",
            "service_type": "Please specify what type of service you need (medical, dental, beauty, etc.)",
            "date": "Please specify when you'd like to book (tomorrow, next Friday, specific date)",
            "time_slot": "Please specify what time you prefer (morning, afternoon, or specific time like 2:30 PM)"
        }
        
        for field in missing_fields:
            if field in field_prompts:
                suggestions.append(field_prompts[field])
        
        return suggestions

    async def _validate_provider(self, provider_name: str, service_type: str) -> Dict[str, Any]:
        """Validate if provider exists using the available API"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"http://127.0.0.1:8003/provider/{provider_name}")
                if response.status_code == 200:
                    print("DEBUG: Provider API response text:", response.text)  # Debug print for troubleshooting
                    try:
                        provider_data = response.json()
                    except Exception as ex:
                        return {
                            "valid": False,
                            "message": f"Provider API did not return valid JSON for '{provider_name}'. Raw response: {response.text}",
                            "suggestions": ["Please try again later"]
                        }
                    # Check if the provider exists and optionally validate service type
                    if provider_data:
                        # If provider data includes service types, validate against them
                        provider_services = provider_data.get("service_types", [])
                        if provider_services and service_type.lower() not in [s.lower() for s in provider_services]:
                            return {
                                "valid": False,
                                "message": f"Provider '{provider_name}' does not offer {service_type} services",
                                "suggestions": [f"Available services: {', '.join(provider_services)}"]
                            }
                        return {"valid": True, "message": "Provider validated"}
                    else:
                        return {
                            "valid": False,
                            "message": f"Provider '{provider_name}' not found",
                            "suggestions": ["Please check the provider name and try again"]
                        }
                elif response.status_code == 404:
                    return {
                        "valid": False,
                        "message": f"Provider '{provider_name}' not found",
                        "suggestions": ["Please check the provider name and try again"]
                    }
                else:
                    return {
                        "valid": False,
                        "message": f"Failed to validate provider: {provider_name}",
                        "suggestions": ["Please try again later"]
                    }
        except Exception as e:
            return {
                "valid": False,
                "message": f"Error validating provider: {str(e)}",
                "suggestions": ["Please try again later"]
            }

    async def _validate_time_slot_with_capacity(self, date: str, time_slot: str, provider: str) -> Dict[str, Any]:
        """Enhanced validation with capacity management and auto-suggestion"""
        try:
            # Parse and validate date
            booking_date = datetime.strptime(date, "%Y-%m-%d")
            
            # Check if date is not in the past
            if booking_date.date() < datetime.now().date():
                return {
                    "status": "invalid",
                    "message": "Cannot book appointments in the past",
                    "suggestions": ["Please choose a future date"]
                }
            
            # Check if date is too far in future
            max_future = datetime.now() + timedelta(days=90)
            if booking_date > max_future:
                return {
                    "status": "invalid",
                    "message": "Cannot book more than 90 days in advance",
                    "suggestions": ["Please choose a date within the next 3 months"]
                }
            
            # Call n8n API to get available slots for the provider and date
            async with httpx.AsyncClient() as client:
                response = await client.get(f"http://127.0.0.1:8003/provider-time-slots/{provider}/{date}")
                if response.status_code != 200:
                    return {
                        "status": "no_slots",
                        "message": f"Failed to fetch available slots for {provider} on {date}",
                        "suggestions": ["Please try again later"]
                    }
                
                # Assuming the API returns data in this format:
                # {"available_slots": [{"time": "09:00", "available_spots": 2, "total_capacity": 5}, ...]}
                api_data = response.json()
                available_slots = api_data.get("available_slots", [])
                
                if not available_slots:
                    return {
                        "status": "no_slots",
                        "message": f"No available slots for {provider} on {date}",
                        "suggestions": ["Please choose a different date"]
                    }
                
                # Normalize requested time slot
                normalized_time = self._normalize_time_slot(time_slot)
                
                # Check if exact requested slot is available with capacity
                for slot in available_slots:
                    if slot["time"] == normalized_time and slot["available_spots"] > 0:
                        return {
                            "status": "exact_match",
                            "confirmed_slot": {
                                "time": slot["time"],
                                "available_spots": slot["available_spots"],
                                "capacity": slot["total_capacity"]
                            }
                        }
                
                # Original slot not available, find alternatives
                alternatives = self._find_alternative_slots(date, normalized_time, available_slots)
                
                if alternatives:
                    # Find the nearest available slot
                    nearest_slot = alternatives[0]  # Already sorted by proximity
                    
                    return {
                        "status": "alternative_found",
                        "message": f"Time slot {time_slot} is not available (full or doesn't exist)",
                        "suggested_slot": nearest_slot,
                        "alternatives": alternatives[:5]  # Limit to top 5 alternatives
                    }
                
                # No alternatives available
                return {
                    "status": "no_capacity",
                    "message": f"No available slots on {date}. All time slots are fully booked.",
                    "suggestions": [
                        "Please try a different date"
                    ]
                }
            
        except ValueError:
            return {
                "status": "invalid",
                "message": f"Invalid date format: {date}",
                "suggestions": ["Please provide date in YYYY-MM-DD format"]
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Error validating time slot: {str(e)}",
                "suggestions": ["Please try again later"]
            }

    def _find_alternative_slots(self, date: str, requested_time: str, available_slots: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Find alternative time slots sorted by proximity to requested time"""
        alternatives = []
        
        try:
            requested_datetime = datetime.strptime(f"{date} {requested_time}", "%Y-%m-%d %H:%M")
        except:
            # If parsing fails, use current time as reference
            requested_datetime = datetime.now().replace(hour=12, minute=0)
        
        for slot in available_slots:
            available_spots = slot["available_spots"]
            
            if available_spots > 0:  # Only include slots with available capacity
                try:
                    slot_datetime = datetime.strptime(f"{date} {slot['time']}", "%Y-%m-%d %H:%M")
                    time_diff = abs((slot_datetime - requested_datetime).total_seconds())
                    
                    alternatives.append({
                        "time": slot["time"],
                        "available_spots": available_spots,
                        "capacity": slot["total_capacity"],
                        "time_difference_minutes": int(time_diff / 60)
                    })
                except:
                    continue
        
        # Sort by time difference (nearest first)
        alternatives.sort(key=lambda x: x["time_difference_minutes"])
        return alternatives

    def _normalize_time_slot(self, time_slot: str) -> str:
        """Convert various time formats to standard HH:MM format"""
        import re
        
        time_slot = time_slot.lower().strip()
        
        # Convert word times to hours
        word_times = {
            "morning": "09:00",
            "afternoon": "14:00", 
            "evening": "18:00",
            "noon": "12:00"
        }
        
        if time_slot in word_times:
            return word_times[time_slot]
        
        # Handle PM/AM format
        am_pm_pattern = r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)'
        match = re.match(am_pm_pattern, time_slot)
        
        if match:
            hour = int(match.group(1))
            minute = int(match.group(2) or 0)
            period = match.group(3)
            
            if period == "pm" and hour != 12:
                hour += 12
            elif period == "am" and hour == 12:
                hour = 0
                
            return f"{hour:02d}:{minute:02d}"
        
        # Try to parse as HH:MM
        time_pattern = r'(\d{1,2}):(\d{2})'
        match = re.match(time_pattern, time_slot)
        if match:
            return f"{int(match.group(1)):02d}:{int(match.group(2)):02d}"
        
        return time_slot

# Initialize validator
validator = IntentValidator()

@app.post("/validate-intent")
async def validate_intent_endpoint(req: Request):
    """Main validation endpoint for A2A communication"""
    try:
        data = await req.json()
        intent_data = IntentData(**data)
        validation_result = await validator.validate_intent(intent_data)
        return validation_result.dict()
        
    except Exception as e:
        return {
            "is_valid": False,
            "validation_result": ValidationResult.MISSING_REQUIRED_DATA,
            "error_message": f"Validation error: {str(e)}",
            "next_action": "return_error"
        }

@app.post("/book-slot")
async def book_slot_endpoint(req: Request):
    """Endpoint to actually book a slot and decrement capacity"""
    try:
        data = await req.json()
        provider_name = data.get("provider_name")
        date = data.get("date")
        time_slot = data.get("time_slot")
        
        # Since we don't have a dedicated booking API, you'll need to implement this
        # based on your n8n workflow. For now, return a mock response
        return {
            "success": True, 
            "message": f"Slot booked for {provider_name} on {date} at {time_slot}",
            "booking_reference": f"REF_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        }
        
    except Exception as e:
        return {"success": False, "message": f"Booking error: {str(e)}"}

@app.get("/available-slots/{provider_name}/{date}")
async def get_available_slots(provider_name: str, date: str):
    """Get all available slots with capacity info for a specific provider and date"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"http://127.0.0.1:8003/provider-time-slots/{provider_name}/{date}")
            if response.status_code != 200:
                return {"error": "Failed to fetch available slots"}
            return response.json()
    except Exception as e:
        return {"error": f"Error fetching available slots: {str(e)}"}

@app.get("/provider/{provider_name}")
async def get_provider_info(provider_name: str):
    """Get provider information"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"http://127.0.0.1:8003/provider/{provider_name}")
            if response.status_code != 200:
                return {"error": "Failed to fetch provider info"}
            return response.json()
    except Exception as e:
        return {"error": f"Error fetching provider info: {str(e)}"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "intent-validator-with-capacity", "n8n_url": N8N_API_BASE_URL}