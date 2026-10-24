# Hostlur — Hostel Life, Simplified.

An AI-assisted hostel complaint management and resident living platform built for college students and hostel wardens. Hostlur centralizes problem reporting across Wi-Fi, water supply, electricity, food quality, cleanliness, maintenance, and safety, eliminating chaotic WhatsApp threads and lost paper logbooks.

The application features official integration with Google's **Gemma 4** open-weights model (`gemma-4-26b-a4b-it`) via the **Google AI Studio API** for multimodal text-and-image complaint triage, while maintaining 100% operational availability through deterministic fallback resilience.

---

## 🌟 Key Features

### 🤝 1. Dual Resolution Verification
A complaint is only marked fully **Resolved** after **BOTH** the warden and the student verify the resolution:
1. **Warden Inspection:** Warden marks repairs complete → status becomes `Pending Student Confirmation`.
2. **Student Verification:** Student inspects the repair and can either:
   - **Confirm Resolution:** Rates satisfaction (1–5 stars) and leaves feedback → ticket closes as `Resolved`.
   - **Reject / Reopen:** If the faucet still drips or Wi-Fi drops, student explains the persistence → ticket escalates to `Reopened`.

### 🎨 2. Black & Yellow Brand Design & Dark/Light Mode
- High-contrast, premium startup aesthetic using deep carbon blacks, warm slate tones, and vibrant golden yellow accents (`#F5CB5C`).
- Seamless **Dark / Light theme toggle** with persistent state across browser sessions.
- Modern SVG Hostlur logo monogram integrated throughout the navbar, landing page, and modals.

### 📸 3. Image Upload + Gemma 4 Multimodal Vision
- Students can attach photos of leaks, broken furniture, sparking switchboards, or maintenance defects.
- Server-side integration with **Gemma 4** (`gemma-4-26b-a4b-it`) analyzes visual evidence and complaint text simultaneously, extracting category, location, duration, and urgency.
- Offline resilience: If AI is unreachable or times out, complaints and images are still saved and categorized via deterministic heuristics.

### 🛡️ 4. Role-Based Login & Student Management
- Separate **Student Login** and **Warden Login** flows with secure PBKDF2-HMAC-SHA256 password hashing.
- Authorized wardens can register student accounts, allocate rooms/floors, and securely reset resident passwords.

### 🍛 5. Mess Timings & 7-Day Rotating Menu
- Daily meal timings (Breakfast, Lunch, Snacks, Dinner).
- Complete 7-day weekly mess menu with nutritious rotation and chef's special notes.

### 🚪 6. Curfew Hours, Announcements & Verified Contacts
- Official campus gate closing and curfew timings (weekday vs weekend).
- Active announcements board from the Warden Office.
- Verified directory for Chief Warden, Wing Caretakers, 24/7 Emergency Helpline, and Campus Ambulance.

### ⚡ 7. Student Profile Auto-Fill
- Automatically populates the student's Hostel Block, Floor, and Room on the complaint form with 1-click override for common areas.

### 📖 8. In-App User Manual
- Interactive walkthrough explaining every button, workflow, and protocol.

---

## 🏗️ Technology Stack

| Component | Technology | Description |
|---|---|---|
| **Backend** | Python 3.14 + FastAPI | High-performance asynchronous REST API with Pydantic v2 schemas |
| **Server** | Uvicorn (ASGI) | Production-ready ASGI server |
| **Database** | SQLite with WAL Mode | Relational database with foreign keys, indexes, timeline tracking, and supporters table |
| **AI Integration** | Google AI Studio API | Multimodal vision & text analysis with `gemma-4-26b-a4b-it` |
| **Frontend** | Vanilla ES6+ & HTML5 | Lightning-fast Single-Page Application (SPA) |
| **Design System** | Custom CSS3 Variables | Black & Yellow theme with Dark/Light mode support |

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
Copy `.env.example`:
```bash
cp .env.example .env
```

Configure your credentials in `.env`:
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

### Step 4: Run the Application
```bash
source .venv/bin/activate
PYTHONPATH=. uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

Open your browser at:
```
http://127.0.0.1:8000
```

OpenAPI Swagger documentation:
```
http://127.0.0.1:8000/docs
```

---

## 🧪 Testing

Run the automated test suite verifying all 7 core subsystems:
```bash
source .venv/bin/activate
PYTHONPATH=. python backend/test_backend.py
```

### Test Coverage Summary:
- ✅ Health check & API metadata (v2.0.0)
- ✅ Student & Warden role login with PBKDF2 password authentication
- ✅ Warden student account creation & password reset
- ✅ Dual resolution verification (Pending confirmation → Reopen or 5-star Close)
- ✅ Verified contacts, Mess timings, 7-day Mess menu, and Curfew rules
- ✅ Deterministic emergency safety hazard detection

---

## 🎯 Demo Credentials for Hackathon Evaluators

| Persona | Role | Email | Password | Scope |
|---|---|---|---|---|
| **Aarav Sharma** | Student | `aarav@campus.edu` | `student123` | Block B (Boys), Room B-302 |
| **Priya Patel** | Student | `priya@campus.edu` | `student123` | Block C (Girls), Room C-204 |
| **Dr. R. K. Sharma** | Warden | `warden.sharma@campus.edu` | `warden123` | Campus-Wide Administration |

*(Use the **1-Click Auto Fill** button in the Sign In modal or the **Demo Role** dropdown in the top navbar).*

---

## 📄 License
MIT License. Built for collegiate hostel communities.
