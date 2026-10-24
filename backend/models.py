from typing import List, Optional
from pydantic import BaseModel, Field

class AIAnalyzeRequest(BaseModel):
    description: str = Field(..., min_length=5, max_length=2000, description="Natural language complaint text")
    hostel_block: Optional[str] = Field(None, max_length=100)
    location: Optional[str] = Field(None, max_length=200)

class AIAnalysisResult(BaseModel):
    category: str
    location: Optional[str] = None
    duration: Optional[str] = None
    suggested_priority: str
    summary: str
    missing_information: List[str] = []
    is_hazard: bool = False
    hazard_reason: Optional[str] = None
    ai_status: str = "success"  # "success" or "fallback"

class ComplaintCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=150)
    category: str = Field(..., min_length=2, max_length=50)
    description: str = Field(..., min_length=10, max_length=2000)
    hostel_block: str = Field(..., min_length=2, max_length=100)
    location: str = Field(..., min_length=2, max_length=200)
    duration: Optional[str] = Field(None, max_length=100)
    suggested_priority: Optional[str] = "Medium"
    summary: Optional[str] = None
    run_ai: bool = True

class StatusUpdateRequest(BaseModel):
    status: str = Field(..., min_length=3, max_length=30)
    note: Optional[str] = Field(None, max_length=500)
    confirmed_priority: Optional[str] = None

class UserProfile(BaseModel):
    id: str
    name: str
    email: str
    role: str  # "student" or "warden"
    hostel_block: Optional[str] = None
    room: Optional[str] = None
