from fastapi import FastAPI, Request
import spacy
import dateparser
from datetime import datetime, timedelta
import re
from typing import Optional, Dict, Any

app = FastAPI()

# Load a more suitable model - en_core_web_md or en_core_web_lg for better entity recognition
# If not available, fallback to sm but with enhanced processing
try:
    nlp = spacy.load("en_core_web_md")
except OSError:
    nlp = spacy.load("en_core_web_sm")

# Enhanced service type patterns using semantic similarity and keywords
SERVICE_PATTERNS = {
    "medical": [
        "doctor", "dr", "physician", "clinic", "hospital", "medical center", 
        "healthcare", "checkup", "consultation", "appointment with doc",
        "see the doctor", "medical appointment", "health center"
    ],
    "dental": [
        "dentist", "dental", "teeth cleaning", "root canal", "dental clinic",
        "orthodontist", "dental care", "tooth", "teeth"
    ],
    "beauty": [
        "salon", "hair", "haircut", "barber", "beauty parlor", "spa",
        "manicure", "pedicure", "facial", "massage", "beauty treatment"
    ],
    "automotive": [
        "mechanic", "garage", "car service", "auto repair", "vehicle",
        "car maintenance", "oil change", "tire", "brake"
    ],
    "legal": [
        "lawyer", "attorney", "legal", "law firm", "consultation",
        "legal advice", "court", "legal services"
    ],
    "fitness": [
        "gym", "trainer", "workout", "fitness", "personal training",
        "exercise", "yoga", "pilates"
    ]
}

def extract_service_type(text: str, doc) -> Optional[str]:
    """Extract service type using multiple approaches"""
    text_lower = text.lower()
    
    # Method 1: Direct keyword matching with context
    for service, keywords in SERVICE_PATTERNS.items():
        for keyword in keywords:
            if keyword in text_lower:
                return service
    
    # Method 2: Use spaCy's entity recognition for organizations
    for ent in doc.ents:
        if ent.label_ == "ORG":
            org_text = ent.text.lower()
            for service, keywords in SERVICE_PATTERNS.items():
                for keyword in keywords:
                    if keyword in org_text:
                        return service
    
    # Method 3: Look for action verbs that might indicate service type
    action_patterns = {
        "medical": ["see", "visit", "consult", "check", "examine"],
        "beauty": ["cut", "style", "trim", "color", "dye"],
        "automotive": ["fix", "repair", "service", "change"],
        "legal": ["consult", "meet", "discuss", "review"]
    }
    
    for service, actions in action_patterns.items():
        for action in actions:
            if action in text_lower:
                # Check if any service keywords appear nearby
                for keyword in SERVICE_PATTERNS[service]:
                    if keyword in text_lower:
                        return service
    
    return None

def extract_enhanced_datetime(text: str, doc) -> Dict[str, Optional[str]]:
    """Enhanced date and time extraction"""
    date = None
    time_slot = None
    
    # First, try spaCy's built-in recognition
    for ent in doc.ents:
        if ent.label_ == "DATE":
            date = ent.text
        elif ent.label_ == "TIME":
            time_slot = ent.text
    
    # Enhanced date parsing with dateparser
    if date:
        try:
            parsed_date = dateparser.parse(
                date, 
                settings={
                    'PREFER_DAY_OF_MONTH': 'first',
                    'PREFER_DATES_FROM': 'future',
                    'RETURN_AS_TIMEZONE_AWARE': False
                }
            )
            if parsed_date:
                date = parsed_date.strftime("%Y-%m-%d")
        except:
            date = None
    
    # If no date found by spaCy, try dateparser on the entire text
    if not date:
        try:
            parsed_date = dateparser.parse(
                text,
                settings={
                    'PREFER_DAY_OF_MONTH': 'first',
                    'PREFER_DATES_FROM': 'future',
                    'RETURN_AS_TIMEZONE_AWARE': False
                }
            )
            if parsed_date:
                date = parsed_date.strftime("%Y-%m-%d")
        except:
            pass
    
    # Enhanced time extraction using regex patterns
    if not time_slot:
        time_patterns = [
            r'\b(\d{1,2}):(\d{2})\s*(am|pm|AM|PM)?\b',
            r'\b(\d{1,2})\s*(am|pm|AM|PM)\b',
            r'\b(morning|afternoon|evening|noon|midnight)\b',
            r'\bat\s+(\d{1,2}(?::\d{2})?(?:\s*(?:am|pm|AM|PM))?)\b'
        ]
        
        for pattern in time_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                time_slot = match.group(0).strip()
                break
    
    return {"date": date, "time_slot": time_slot}

def extract_provider_name(text: str, doc) -> Optional[str]:
    """Enhanced provider name extraction"""
    # Look for person names
    for ent in doc.ents:
        if ent.label_ == "PERSON":
            return ent.text
    
    # Look for organization names
    for ent in doc.ents:
        if ent.label_ == "ORG":
            return ent.text
    
    # Look for patterns like "Dr. Smith", "with John", etc.
    patterns = [
        r'\b(?:Dr\.?|Doctor)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b',
        r'\bwith\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b',
        r'\bat\s+([A-Z][a-zA-Z\s&]+(?:Clinic|Hospital|Center|Salon|Shop))\b'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    
    return None

@app.post("/extract-intent")
async def extract_intent(req: Request):
    try:
        data = await req.json()
        text = data.get("text", "")
        
        if not text.strip():
            return {
                "error": "Empty text provided",
                "provider_name": None,
                "time_slot": None,
                "service_type": None,
                "date": None,
            }
        
        # Process text with spaCy
        doc = nlp(text)
        
        # Extract all components
        provider_name = extract_provider_name(text, doc)
        service_type = extract_service_type(text, doc)
        datetime_info = extract_enhanced_datetime(text, doc)
        
        # Additional context extraction
        intent_confidence = "high" if all([provider_name, service_type, datetime_info["date"]]) else "medium"
        
        response = {
            "provider_name": provider_name,
            "time_slot": datetime_info["time_slot"],
            "service_type": service_type,
            "date": datetime_info["date"],
            "confidence": intent_confidence,
            "entities_found": {
                "provider": bool(provider_name),
                "service": bool(service_type),
                "date": bool(datetime_info["date"]),
                "time": bool(datetime_info["time_slot"])
            }
        }
        
        return response
        
    except Exception as e:
        return {
            "error": f"Processing error: {str(e)}",
            "provider_name": None,
            "time_slot": None,
            "service_type": None,
            "date": None,
        }

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy", "model": nlp.meta["name"]}

# Test endpoint for debugging
@app.post("/debug-extract")
async def debug_extract(req: Request):
    """Debug endpoint to see all extracted entities"""
    data = await req.json()
    text = data.get("text", "")
    doc = nlp(text)
    
    entities = []
    for ent in doc.ents:
        entities.append({
            "text": ent.text,
            "label": ent.label_,
            "start": ent.start_char,
            "end": ent.end_char
        })
    
    return {
        "text": text,
        "entities": entities,
        "tokens": [{"text": token.text, "pos": token.pos_, "lemma": token.lemma_} for token in doc]
    }