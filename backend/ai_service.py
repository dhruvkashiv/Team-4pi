import re
import json
import logging
from typing import Optional, Tuple
import httpx

from backend.config import (
    GOOGLE_AI_API_KEY,
    GEMMA_MODEL,
    ALLOWED_CATEGORIES,
    ALLOWED_PRIORITIES,
    HAZARD_KEYWORDS
)
from backend.models import AIAnalysisResult

logger = logging.getLogger("hostlur.ai")

def detect_hazards(text: str) -> Tuple[bool, Optional[str]]:
    """Deterministic safety rule check for physical and electrical hazards."""
    lowered = text.lower()
    for kw in HAZARD_KEYWORDS:
        if kw in lowered:
            return True, f"Emergency safety rule triggered: '{kw}' detected in complaint description."
    return False, None

def heuristic_fallback_analysis(text: str, hostel_block: Optional[str] = None, location: Optional[str] = None) -> AIAnalysisResult:
    """Deterministic fallback if AI service is offline, timed out, or unavailable."""
    lowered = text.lower()
    is_hazard, hazard_reason = detect_hazards(text)

    # Determine category via keyword heuristics
    category = "Other"
    if any(k in lowered for k in ["wifi", "wi-fi", "internet", "router", "lan", "net", "slow net", "ping"]):
        category = "Wi-Fi and Internet"
    elif any(k in lowered for k in ["water", "geyser", "tap", "shower", "pipe", "leak", "flush", "drain"]):
        category = "Water Supply"
    elif any(k in lowered for k in ["light", "fan", "electricity", "socket", "switch", "power", "bulb", "tube", "ac"]):
        category = "Electricity"
    elif any(k in lowered for k in ["food", "mess", "canteen", "lunch", "dinner", "breakfast", "meal"]):
        category = "Food Quality"
    elif any(k in lowered for k in ["clean", "dirt", "garbage", "trash", "dustbin", "smell", "odor", "bathroom"]):
        category = "Cleanliness"
    elif any(k in lowered for k in ["door", "lock", "window", "bed", "chair", "table", "cupboard", "latch"]):
        category = "Maintenance"
    elif any(k in lowered for k in ["theft", "stolen", "harassment", "guard", "security", "gate"]):
        category = "Safety"

    # Determine priority
    if is_hazard:
        priority = "Urgent"
    elif any(k in lowered for k in ["urgent", "immediately", "exam", "cannot study", "no water", "blackout", "overflow"]):
        priority = "High"
    elif any(k in lowered for k in ["slow", "sometimes", "mild", "noisy", "creaking"]):
        priority = "Low"
    else:
        priority = "Medium"

    # Generate summary
    clean_text = text.strip().replace("\n", " ")
    summary = clean_text[:110] + "..." if len(clean_text) > 110 else clean_text

    missing = []
    if not location and not any(k in lowered for k in ["room", "floor", "washroom", "corridor", "bathroom", "wing"]):
        missing.append("Specific room or floor location")

    return AIAnalysisResult(
        category=category,
        location=location or ("Detected in text" if "floor" in lowered or "room" in lowered else None),
        duration="Recent" if "since" in lowered or "today" in lowered else None,
        suggested_priority=priority,
        summary=summary,
        missing_information=missing,
        is_hazard=is_hazard,
        hazard_reason=hazard_reason,
        ai_status="fallback"
    )

async def analyze_complaint_with_gemma(
    description: str,
    hostel_block: Optional[str] = None,
    location: Optional[str] = None
) -> AIAnalysisResult:
    """
    Calls Google AI Studio API using the configured Gemma model.
    Extracts category, priority, concise summary, and checks for hazards.
    Falls back gracefully to deterministic rule-based analysis on any error.
    """
    # 1. Deterministic safety check
    is_hazard, hazard_reason = detect_hazards(f"{description} {location or ''}")

    # If no API key configured, use fallback immediately
    if not GOOGLE_AI_API_KEY:
        logger.warning("GOOGLE_AI_API_KEY not configured. Using deterministic fallback.")
        res = heuristic_fallback_analysis(description, hostel_block, location)
        if is_hazard:
            res.is_hazard = True
            res.hazard_reason = hazard_reason
            res.suggested_priority = "Urgent"
        return res

    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMMA_MODEL}:generateContent?key={GOOGLE_AI_API_KEY}"

    categories_str = ", ".join(ALLOWED_CATEGORIES)
    priorities_str = ", ".join(ALLOWED_PRIORITIES)

    prompt = f"""You are Hostlur AI, an intelligent assistant for a college hostel complaint portal.
A student has reported the following problem:
"{description}"
Hostel Block: {hostel_block or 'Not specified'}
Location: {location or 'Not specified'}

Analyze the complaint and reply STRICTLY with a single valid JSON object.
Allowed categories: [{categories_str}]
Allowed priorities: [{priorities_str}]

Required JSON structure:
{{
  "category": "Choose exactly one from the allowed categories list",
  "location": "Specific location mentioned (e.g. 3rd floor, Room 302) or null",
  "duration": "Duration stated (e.g. since morning, 2 days) or null",
  "suggested_priority": "One of: Low, Medium, High, Urgent",
  "summary": "Factual 1-sentence summary under 120 characters",
  "missing_information": ["List any key missing details that would help the warden resolve this faster"]
}}"""

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ]
    }

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(endpoint, json=payload)

        if resp.status_code != 200:
            logger.error(f"Gemma API returned HTTP {resp.status_code}: {resp.text[:200]}")
            fallback = heuristic_fallback_analysis(description, hostel_block, location)
            if is_hazard:
                fallback.is_hazard = True
                fallback.hazard_reason = hazard_reason
                fallback.suggested_priority = "Urgent"
            return fallback

        data = resp.json()
        candidates = data.get("candidates", [])
        if not candidates:
            raise ValueError("No candidates returned from Gemma API")

        parts = candidates[0].get("content", {}).get("parts", [])
        # Gemma 4 marks chain-of-thought with 'thought: true'. Extract non-thought parts.
        response_text = ""
        for p in parts:
            if not p.get("thought", False) and "text" in p:
                response_text += p["text"]

        if not response_text and parts:
            response_text = parts[-1].get("text", "")

        # Extract JSON from markdown fence or raw text
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", response_text, re.DOTALL)
        if json_match:
            raw_json = json_match.group(1)
        else:
            json_match = re.search(r"(\{.*\})", response_text, re.DOTALL)
            raw_json = json_match.group(1) if json_match else response_text

        parsed = json.loads(raw_json)

        # Validate category
        raw_cat = parsed.get("category", "Other")
        category = "Other"
        for allowed in ALLOWED_CATEGORIES:
            if allowed.lower() in raw_cat.lower() or raw_cat.lower() in allowed.lower():
                category = allowed
                break

        # Validate priority
        raw_prio = parsed.get("suggested_priority", "Medium")
        priority = "Medium"
        for allowed_p in ALLOWED_PRIORITIES:
            if allowed_p.lower() == raw_prio.lower():
                priority = allowed_p
                break

        # Override priority if deterministic hazard was found
        if is_hazard:
            priority = "Urgent"

        missing_info = parsed.get("missing_information", [])
        if not isinstance(missing_info, list):
            missing_info = []

        summary = parsed.get("summary", description[:100]).strip()
        extracted_location = parsed.get("location") or location
        duration = parsed.get("duration")

        return AIAnalysisResult(
            category=category,
            location=extracted_location,
            duration=duration,
            suggested_priority=priority,
            summary=summary,
            missing_information=missing_info,
            is_hazard=is_hazard,
            hazard_reason=hazard_reason,
            ai_status="success"
        )

    except Exception as exc:
        logger.error(f"Error calling or parsing Gemma API: {str(exc)}")
        fallback = heuristic_fallback_analysis(description, hostel_block, location)
        if is_hazard:
            fallback.is_hazard = True
            fallback.hazard_reason = hazard_reason
            fallback.suggested_priority = "Urgent"
        return fallback
