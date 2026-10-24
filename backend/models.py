from typing import List, Optional
from pydantic import BaseModel, Field

class AIAnalyzeRequest(BaseModel):
    description: Optional[str] = Field("", max_length=2000, description="Natural language complaint text")
    hostel_block: Optional[str] = Field(None, max_length=100)
    location: Optional[str] = Field(None, max_length=200)
    image_data: Optional[str] = Field(None, description="Base64 encoded image or data URL for Gemma 4 vision analysis")

class AIAnalysisResult(BaseModel):
    category: str
    subcategory: Optional[str] = None
    description: Optional[str] = None
    visual_evidence: List[str] = []
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    needs_human_review: bool = False
    suggested_priority: str = "Medium"
    summary: str
    location: Optional[str] = None
    duration: Optional[str] = None
    missing_information: List[str] = []
    is_hazard: bool = False
    hazard_reason: Optional[str] = None
    ai_status: str = "success"  # "success" or "fallback"
    image_analyzed: bool = False

class ComplaintCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=150)
    category: str = Field(..., min_length=2, max_length=60)
    description: str = Field(..., min_length=5, max_length=2000)
    hostel_block: str = Field(..., min_length=2, max_length=100)
    floor: Optional[str] = Field(None, max_length=50)
    location: str = Field(..., min_length=2, max_length=200)
    duration: Optional[str] = Field(None, max_length=100)
    suggested_priority: Optional[str] = "Medium"
    summary: Optional[str] = None
    run_ai: bool = True
    image_url: Optional[str] = None

class StatusUpdateRequest(BaseModel):
    status: str = Field(..., min_length=3, max_length=40)
    note: Optional[str] = Field(None, max_length=500)
    confirmed_priority: Optional[str] = None

class StudentResolutionRequest(BaseModel):
    action: str = Field(..., description="'confirm' or 'reject'")
    rating: Optional[int] = Field(None, ge=1, le=5)
    feedback: Optional[str] = Field(None, max_length=500)
    reopen_reason: Optional[str] = Field(None, max_length=500)

class UserProfile(BaseModel):
    id: str
    name: str
    email: str
    role: str  # "student" or "warden"
    hostel_block: Optional[str] = None
    floor: Optional[str] = None
    room: Optional[str] = None
    phone: Optional[str] = None

class LoginRequest(BaseModel):
    email_or_id: str = Field(..., min_length=2, max_length=100)
    password: str = Field(..., min_length=3, max_length=100)
    role: Optional[str] = None  # Expected role check ("student" or "warden")

class LoginResponse(BaseModel):
    token: str
    user: UserProfile
    message: str = "Login successful"

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=6)

class StudentCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    email: str = Field(..., min_length=5, max_length=100)
    hostel_block: str = Field(..., min_length=2, max_length=100)
    floor: str = Field(..., min_length=1, max_length=50)
    room: str = Field(..., min_length=1, max_length=50)
    phone: Optional[str] = Field(None, max_length=30)
    initial_password: Optional[str] = None

class StudentProfileUpdateRequest(BaseModel):
    phone: Optional[str] = Field(None, max_length=30)
    room: Optional[str] = Field(None, max_length=50)
    floor: Optional[str] = Field(None, max_length=50)

class ImageUploadResponse(BaseModel):
    image_url: str
    filename: str
    message: str = "Image uploaded successfully"
