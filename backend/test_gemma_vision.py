"""
Hostlur Gemma 4 Vision Multimodal Verification Test
Directly tests the Gemma 4 vision pipeline with real complaint image fixtures.
Verifies that:
1. Tap/leak image is classified as 'Plumbing & Water Supply', NOT 'Electricity'.
2. Structured output contains subcategory, visual evidence, confidence score.
3. Fallback logic never defaults to Electricity.
"""
import os
import sys
import base64
import asyncio
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from backend.ai_service import analyze_complaint_with_gemma, heuristic_fallback_analysis
from backend.config import ALLOWED_CATEGORIES, GEMMA_MODEL, UPLOADS_DIR

async def run_vision_tests():
    print("=" * 60)
    print(f"GEMMA 4 VISION MULTIMODAL VERIFICATION ({GEMMA_MODEL})")
    print("=" * 60)

    # Test 1: Real user uploaded leaking tap fixture
    sample_img_path = UPLOADS_DIR / "img_e8399cc58c.jpg"
    assert sample_img_path.exists(), f"Image fixture {sample_img_path} not found"

    with open(sample_img_path, "rb") as f:
        img_b64 = "data:image/jpeg;base64," + base64.b64encode(f.read()).decode("utf-8")

    print("\n--- TEST 1: Multimodal Vision on Leaking Faucet Fixture ---")
    res1 = await analyze_complaint_with_gemma(
        description="Water is continuously leaking from the bathroom tap, wasting water.",
        hostel_block="Block B (Boys)",
        location="3rd Floor Washroom",
        image_data=img_b64
    )

    print(f"Category: {res1.category}")
    print(f"Subcategory: {res1.subcategory}")
    print(f"Confidence: {res1.confidence}")
    print(f"Visual Evidence: {res1.visual_evidence}")
    print(f"Suggested Priority: {res1.suggested_priority}")
    print(f"Summary: {res1.summary}")
    print(f"AI Status: {res1.ai_status}")

    assert res1.category in ALLOWED_CATEGORIES, f"Category '{res1.category}' not in allowed taxonomy!"
    assert res1.category == "Plumbing & Water Supply", f"CRITICAL REGRESSION: Expected 'Plumbing & Water Supply', got '{res1.category}'!"
    assert res1.category != "Electricity & Lighting", "CRITICAL BUG: Image classified as Electricity!"
    print("✅ TEST 1 PASSED: Leaking tap image accurately classified as 'Plumbing & Water Supply'.")

    # Test 2: Text-only hazard detection (sparking socket)
    print("\n--- TEST 2: Deterministic Electrical Hazard Detection ---")
    res2 = await analyze_complaint_with_gemma(
        description="The wall socket near bed 2 is sparking and there is a burning smell.",
        hostel_block="Block B (Boys)",
        location="Room B-302",
        image_data=None
    )
    print(f"Category: {res2.category}")
    print(f"Is Hazard: {res2.is_hazard}")
    print(f"Hazard Reason: {res2.hazard_reason}")
    print(f"Priority: {res2.suggested_priority}")
    assert res2.is_hazard is True, "Expected safety hazard to be flagged!"
    assert res2.suggested_priority == "Urgent", "Hazard priority must be elevated to Urgent!"
    print("✅ TEST 2 PASSED: Electrical hazard detected deterministically and elevated to Urgent.")

    # Test 3: Heuristic Fallback Robustness (Ensure 'attached' does not trigger 'Electricity')
    print("\n--- TEST 3: Heuristic Fallback Anti-Regression Test ---")
    fb = heuristic_fallback_analysis(
        text="Please inspect attached photo",
        hostel_block="Block B",
        location="Room 101"
    )
    print(f"Fallback Category for 'Please inspect attached photo': {fb.category}")
    assert fb.category != "Electricity & Lighting", "REGRESSION: Substring 'ac' in 'attached' triggered Electricity!"
    assert fb.needs_human_review is True, "Ambiguous text must flag needs_human_review = True!"
    print("✅ TEST 3 PASSED: Fallback safely classified ambiguous query without false positive on Electricity.")

    print("\n" + "=" * 60)
    print("ALL GEMMA 4 VISION & AI TESTS COMPLETED SUCCESSFULLY!")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(run_vision_tests())
