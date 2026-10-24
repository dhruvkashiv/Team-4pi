# Hostlur — Hostel Life, Simplified.

An AI-assisted hostel complaint management platform built for college students and hostel wardens. Hostlur centralizes problem reporting across Wi-Fi, water supply, electricity, food quality, cleanliness, maintenance, and safety, eliminating chaotic WhatsApp threads and lost paper logbooks.

The application features official integration with Google's **Gemma** open-weights model (`gemma-4-26b-a4b-it`) via the **Google AI Studio API** for natural-language complaint triage, while maintaining 100% operational availability through deterministic fallback resilience.

---

## 🌟 Key Features

### 🎓 For Students
- **Report in Under 60 Seconds**: Simple, responsive complaint form with automatic block, location, and issue details.
- **✨ Auto-Analyze with Gemma AI**: Real-time natural language triage that identifies category, urgency, duration, and extracts a concise factual summary before submission.
- **Similar Issue Discovery & Upvoting**: Discovers existing open complaints in the student's block and allows 1-click **+1 Support** to amplify recurring issues rather than creating duplicates.
- **Real-Time Status Tracking**: Follow tickets through `Submitted` → `Under Review` → `In Progress` → `Resolved` with full technician notes.

### 🛡️ For Hostel Wardens & Administrators
- **Real-Time Operational Triage**: Live metrics on total open complaints, urgent hazards, in-progress tasks, and resolved issues.
- **🚨 Deterministic Safety Hazard Detection**: Instant safety alerts for high-risk hazards (sparks, burning, short circuits, gas leaks, structural cracks) overriding AI suggestions with mandatory human inspection flags.
- **Role-Restricted Status Management**: Server-side authorized status and confirmed priority updates with a permanent, timestamped audit history.
- **Comprehensive Filtering**: Search and filter by hostel block, issue category, urgency level, and resolution status.

---

## 🏗️ Technology Stack

| Component | Technology | Description |
|-----------|------------|-------------|
| **Backend** | Python 3.14 + FastAPI | High-performance asynchronous REST API with Pydantic v2 validation |
| **Server** | Uvicorn (ASGI) | Production-ready ASGI server |
| **Database** | SQLite with WAL Mode | Relational database with foreign keys, indexes, timeline tracking, and supporters table |
| **AI Integration** | Google AI Studio API | Direct integration with `gemma-4-26b-a4b-it` |
| **Frontend** | Vanilla ES6+ & HTML5 | Lightweight, lightning-fast Single-Page Application (SPA) |
| **Design System** | Custom CSS3 Variables | Brand palette: Alabaster Grey, Soft Linen, Tuscan Sun, Carbon Black, Graphite |

---

## 🎨 Brand Design System

Hostlur uses a student-focused, warm, and sophisticated color palette:

- **Alabaster Grey** (`#CFDBD5`): Page background
- **Soft Linen** (`#E8EDDF`): Main content canvas and cards
- **Tuscan Sun** (`#F5CB5C`): Primary highlights and action buttons
- **Carbon Black** (`#242423`): High-contrast typography and headings
- **Graphite** (`#333533`): Secondary text
- **Warm White** (`#FFFFFF`): Dashboard panels and form inputs
- **Soft Lavender** (`#DCD2F5`): Gemma AI suggestion badges and callouts
- **Soft Green** (`#D5E8D8`): Resolved status badges
- **Soft Coral** (`#F5D3CF` / `#900C05`): Urgent hazards

---

## 🧠 Google Gemma 4 Model Integration

Hostlur connects to the official Google AI Studio API:

```
POST https://generativelanguage.googleapis.com/v1beta/models/gemma-4-26b-a4b-it:generateContent?key={GOOGLE_AI_API_KEY}
```

### 1. Robust Output & Thought Filtering
Gemma 4 models utilize internal chain-of-thought tokens (`"thought": true`). Hostlur's dedicated `backend/ai_service.py` filters non-thought candidate response parts, extracts JSON from code fences, and validates against strict Pydantic schemas.

### 2. Deterministic Safety & Hazard Rules
Language models are never solely relied upon for emergencies. Hostlur scans complaint text for critical hazard keywords (e.g. `spark`, `smoke`, `burning`, `short circuit`, `live wire`, `gas leak`). If detected:
- Priority is automatically elevated to **Urgent**.
- The record is flagged with `is_hazard = True`.
- An alert is highlighted on the warden dashboard for immediate manual intervention.

### 3. Graceful Fallback (AI-Independent Core)
Even if the Google AI API key is missing, network is offline, or rate limits occur:
- Complaint submission and persistence **never fail**.
- A deterministic rule-based heuristic automatically categorizes the issue and generates safe defaults.
- The complaint enters the normal resolution lifecycle seamlessly.

---

## 🚀 Quickstart & Local Installation

### Prerequisites
- Python 3.10+ (Tested on Python 3.14)
- Google AI Studio API Key

### Step 1: Clone and Enter the Directory
```bash
cd hostlur
```

### Step 2: Set Up Python Virtual Environment
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Step 3: Configure Environment Variables
Copy the example environment configuration:
```bash
cp .env.example .env
```

Edit `.env` to configure your Google AI Studio credentials:
```env
HOST=127.0.0.1
PORT=8000
DEBUG=true

# Google AI Studio API Configuration
GOOGLE_AI_API_KEY=your_google_ai_studio_api_key_here
GEMMA_MODEL=gemma-4-26b-a4b-it

# Database Configuration
DATABASE_URL=sqlite:///./hostlur.db
```

> **Security Note:** `.env` is ignored by Git in `.gitignore`. Never commit API keys to version control.

### Step 4: Run the Application
```bash
source .venv/bin/activate
PYTHONPATH=. uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

Open your browser and navigate to:
```
http://127.0.0.1:8000
```

Interactive OpenAPI Swagger documentation is available at:
```
http://127.0.0.1:8000/docs
```

---

## 🧪 Testing

Run the automated test suite verifying all 9 core subsystems:
```bash
source .venv/bin/activate
PYTHONPATH=. python backend/test_backend.py
```

### Test Coverage Summary:
- ✅ Health check & API metadata
- ✅ Role-based session authentication (`student` vs `warden`)
- ✅ Real database metrics computation
- ✅ Complaint persistence and timeline initialization
- ✅ Duplicate / related issue matching
- ✅ +1 Support / upvoting toggle
- ✅ Warden authorization enforcement (HTTP 403 when students attempt privileged status changes)
- ✅ Deterministic emergency hazard detection
- ✅ Graceful AI fallback resilience

---

## 🎯 Hackathon Demonstration Guide

Hostlur includes a built-in **Demo Role Switcher** in the top navigation bar:

1. **Student Persona (Aarav Sharma - Block B)**:
   - View your existing complaints and live counts.
   - Click **+ Report Issue**.
   - Type a natural-language description: *"The Wi-Fi in the 3rd floor west corridor has been dropping constantly since morning."*
   - Click **✨ Auto-Analyze with Gemma AI** to observe real-time AI classification and priority assignment.
   - Submit the issue and watch it appear in the dashboard feed.
2. **Safety Hazard Demo**:
   - Submit a complaint with text: *"The bathroom geyser switch is sparking and water is dripping on the socket!"*
   - Observe the instant **🚨 Safety Hazard Alert** and automatic Urgent priority assignment.
3. **Warden Persona (Dr. R. K. Sharma)**:
   - Switch persona to **🛡️ Warden: Dr. Sharma**.
   - Open the **Hostel Warden Portal**.
   - View the highlighted urgent hazard ticket.
   - Click **Manage & Update →**, change status to `In Progress`, add a note *"Electrician dispatched"*, and save.
   - Notice the updated status reflected in the complaint timeline.

---

## 📄 License
MIT License. Built for collegiate hostel communities.
