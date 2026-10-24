import re
import json
import logging
from typing import Optional, Tuple, Dict, Any
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

def heuristic_fallback_analysis(
    text: str,
    hostel_block: Optional[str] = None,
    location: Optional[str] = None,
    had_image: bool = False
) -> AIAnalysisResult:
    """
    Deterministic rule-based fallback if the AI vision service is offline or unreachable.
    Uses strict word boundaries to avoid false positives (e.g. 'attached' matching 'ac').
    Defaults to 'Other / Unclear' with human review flag if no pattern matches.
    """
    lowered = text.lower()
    is_hazard, hazard_reason = detect_hazards(text)

    # Use strict regex with word boundaries
    category = "Other / Unclear"
    subcategory = "Unspecified issue"
    evidence = []

    if re.search(r"\b(wifi|wi-fi|internet|router|lan|ethernet|network|signal|ping)\b", lowered):
        category = "Internet & Networking"
        subcategory = "Network equipment or Wi-Fi outage"
        evidence.append("Keywords referencing networking/internet connectivity.")
    elif re.search(r"\b(water|pipe|leak|tap|faucet|geyser|drain|flush|shower|overflow|plumbing)\b", lowered):
        category = "Plumbing & Water Supply"
        subcategory = "Plumbing fixture or water leakage"
        evidence.append("Keywords referencing plumbing fixtures or water leakage.")
    elif re.search(r"\b(toilet|washroom|commode|urinal|washbasin|sanitation)\b", lowered):
        category = "Washroom & Sanitation"
        subcategory = "Sanitary fixture issue"
        evidence.append("Keywords referencing washroom sanitation.")
    elif re.search(r"\b(light|fan|bulb|tube|socket|switch|short circuit|power|spark|wire|wiring|fuse|\bac\b|air conditioner)\b", lowered):
        category = "Electricity & Lighting"
        subcategory = "Electrical fixture or wiring defect"
        evidence.append("Keywords referencing electrical components or lighting.")
    elif re.search(r"\b(food|mess|canteen|lunch|dinner|breakfast|meal|caterer)\b", lowered):
        category = "Mess & Food"
        subcategory = "Dining or food quality concern"
        evidence.append("Keywords referencing hostel food or mess facilities.")
    elif re.search(r"\b(clean|dirt|dust|garbage|trash|bin|smell|odor|pest|cockroach|insects)\b", lowered):
        category = "Cleaning & Hygiene"
        subcategory = "Cleaning or waste disposal"
        evidence.append("Keywords referencing hygiene or cleaning.")
    elif re.search(r"\b(chair|desk|bed|table|cupboard|almirah|mattress|wardrobe)\b", lowered):
        category = "Furniture & Fixtures"
        subcategory = "Room furniture damage"
        evidence.append("Keywords referencing hostel furniture.")
    elif re.search(r"\b(wall|ceiling|floor|door|window|crack|seepage|hinge|latch|plaster|concrete)\b", lowered):
        category = "Civil & Structural Damage"
        subcategory = "Civil structural defect"
        evidence.append("Keywords referencing building structure or carpentry.")
    elif re.search(r"\b(theft|stolen|guard|security|lock|harassment|gate)\b", lowered):
        category = "Safety & Security"
        subcategory = "Security or access control"
        evidence.append("Keywords referencing hostel security.")

    if is_hazard:
        priority = "Urgent"
    elif any(k in lowered for k in ["urgent", "immediately", "exam", "cannot study", "no water", "blackout"]):
        priority = "High"
    elif any(k in lowered for k in ["slow", "mild", "noisy", "squeaking"]):
        priority = "Low"
    else:
        priority = "Medium"

    clean_text = text.strip().replace("\n", " ")
    if not clean_text or clean_text == "Please inspect attached image":
        summary = f"{category} reported. Manual inspection recommended."
    else:
        summary = clean_text[:110] + "..." if len(clean_text) > 110 else clean_text

    return AIAnalysisResult(
        category=category,
        subcategory=subcategory,
        description=summary,
        visual_evidence=evidence if evidence else ["Fallback heuristic based on text."],
        confidence=0.60 if category != "Other / Unclear" else 0.30,
        needs_human_review=True,
        suggested_priority=priority,
        summary=summary,
        location=location,
        duration="Recent",
        missing_information=[],
        is_hazard=is_hazard,
        hazard_reason=hazard_reason,
        ai_status="fallback",
        image_analyzed=had_image
    )

async def analyze_complaint_with_gemma(
    description: str = "",
    hostel_block: Optional[str] = None,
    location: Optional[str] = None,
    image_data: Optional[str] = None
) -> AIAnalysisResult:
    """
    Calls Google AI Studio API using Gemma 4 (gemma-4-26b-a4b-it).
    Performs multimodal vision classification against the 10 authoritative hostel categories.
    Returns a strict structured JSON result matching the required schema.
    """
    has_image = bool(image_data and len(image_data) > 50)
    is_hazard, hazard_reason = detect_hazards(f"{description} {location or ''}")

    # If no API key configured, use fallback immediately
    if not GOOGLE_AI_API_KEY:
        logger.warning("GOOGLE_AI_API_KEY not configured. Using deterministic fallback.")
        res = heuristic_fallback_analysis(description, hostel_block, location, has_image)
        if is_hazard:
            res.is_hazard = True
            res.hazard_reason = hazard_reason
            res.suggested_priority = "Urgent"
        return res

    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMMA_MODEL}:generateContent?key={GOOGLE_AI_API_KEY}"

    categories_formatted = "\n".join([f"{i+1}. {cat}" for i, cat in enumerate(ALLOWED_CATEGORIES)])

    prompt = f"""You are an expert AI facilities inspector for Hostlur, a university hostel management system.
Inspect the attached image and student complaint text:
Student text: "{description if description else 'Please inspect the attached photo'}"
Hostel Block: {hostel_block or 'Not specified'}
Location: {location or 'Not specified'}

TASK:
1. Examine the visual evidence in the image and text.
2. Classify the problem into EXACTLY ONE of the following 10 approved categories:
{categories_formatted}

3. Return STRICTLY a JSON object with this schema (do not include explanations outside the JSON):
```json
{{
  "category": "Exact name from the 10 approved categories",
  "subcategory": "Specific item or component affected (e.g. Leaking faucet, Damaged socket, Broken chair)",
  "description": "Factual 1-sentence description of the visible defect",
  "visual_evidence": [
    "Specific visual clue 1 observed in image",
    "Specific visual clue 2 observed in image"
  ],
  "confidence": 0.95,
  "needs_human_review": false,
  "suggested_priority": "Low, Medium, High, or Urgent"
}}
```

Rules:
- If the image is blurry, irrelevant, or lacks visual evidence, set category to "Other / Unclear" and needs_human_review to true.
- Do NOT guess Electricity unless there is actual visible electrical equipment (switch, socket, wire, light fixture, breaker).
- Water taps, pipes, or geyser water leaks must be classified as "Plumbing & Water Supply".
- Broken chairs, tables, or beds must be classified as "Furniture & Fixtures".
- Wall cracks, ceiling seepage, or broken doors must be classified as "Civil & Structural Damage".
- Output only valid JSON.
"""

    parts = [{"text": prompt}]

    # Multimodal image attachment
    if has_image:
        try:
            mime_type = "image/jpeg"
            clean_b64 = image_data
            if image_data.startswith("data:"):
                header, clean_b64 = image_data.split(",", 1)
                if "png" in header:
                    mime_type = "image/png"
                elif "webp" in header:
                    mime_type = "image/webp"

            parts.append({
                "inline_data": {
                    "mime_type": mime_type,
                    "data": clean_b64
                }
            })
        except Exception as img_err:
            logger.warning(f"Failed to prepare image part for Gemma 4: {img_err}")

    payload = {
        "contents": [
            {
                "parts": parts
            }
        ]
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(endpoint, json=payload)

        if resp.status_code != 200:
            logger.error(f"Gemma API returned HTTP {resp.status_code}: {resp.text[:300]}")
            fallback = heuristic_fallback_analysis(description, hostel_block, location, has_image)
            if is_hazard:
                fallback.is_hazard = True
                fallback.hazard_reason = hazard_reason
                fallback.suggested_priority = "Urgent"
            return fallback

        data = resp.json()
        candidates = data.get("candidates", [])
        if not candidates:
            raise ValueError("No candidates returned from Gemma API")

        parts_out = candidates[0].get("content", {}).get("parts", [])
        
        # Look specifically for non-thought parts or the last part containing JSON
        response_text = ""
        for p in parts_out:
            if not p.get("thought", False) and "text" in p:
                response_text += p["text"]

        if not response_text and parts_out:
            response_text = parts_out[-1].get("text", "")

        # Extract JSON block
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", response_text, re.DOTALL)
        if json_match:
            raw_json = json_match.group(1)
        else:
            # Non-greedy search for JSON object
            json_match = re.search(r"(\{\s*\"category\".*?\})", response_text, re.DOTALL)
            raw_json = json_match.group(1) if json_match else response_text

        parsed = json.loads(raw_json)

        # Validate category against the 10 approved categories
        raw_cat = parsed.get("category", "").strip()
        matched_cat = "Other / Unclear"
        for allowed in ALLOWED_CATEGORIES:
            if allowed.lower() == raw_cat.lower() or allowed.lower() in raw_cat.lower():
                matched_cat = allowed
                break

        # Validate priority
        raw_prio = parsed.get("suggested_priority", "Medium")
        priority = "Medium"
        for allowed_p in ALLOWED_PRIORITIES:
            if allowed_p.lower() == raw_prio.lower():
                priority = allowed_p
                break

        if is_hazard:
            priority = "Urgent"

        subcategory = parsed.get("subcategory", "General defect")
        desc_text = parsed.get("description", description if description else "Issue inspected via visual evidence.")
        evidence = parsed.get("visual_evidence", [])
        if not isinstance(evidence, list):
            evidence = [str(evidence)]

        confidence_val = float(parsed.get("confidence", 0.85))
        confidence_val = max(0.0, min(1.0, confidence_val))
        needs_review = bool(parsed.get("needs_human_review", False))

        return AIAnalysisResult(
            category=matched_cat,
            subcategory=subcategory,
            description=desc_text,
            visual_evidence=evidence,
            confidence=confidence_val,
            needs_human_review=needs_review or (matched_cat == "Other / Unclear"),
            suggested_priority=priority,
            summary=desc_text,
            location=location,
            duration=None,
            missing_information=[],
            is_hazard=is_hazard,
            hazard_reason=hazard_reason,
            ai_status="success",
            image_analyzed=has_image
        )

    except Exception as exc:
        logger.error(f"Error calling or parsing Gemma API: {str(exc)}")
        fallback = heuristic_fallback_analysis(description, hostel_block, location, has_image)
        if is_hazard:
            fallback.is_hazard = True
            fallback.hazard_reason = hazard_reason
            fallback.suggested_priority = "Urgent"
        return fallback
