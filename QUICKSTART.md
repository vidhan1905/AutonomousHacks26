# Hospital AI Assistant - Quick Start Guide

## Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL database
- UV package manager
- OpenAI API key

## Setup

### 1. Install UV (if not installed)
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Backend Setup

```bash
# Install dependencies
uv sync

# Setup environment variables
cp .env.example .env
# Edit .env with your database URL and OpenAI API key

# Create database if it doesn't exist
uv run python scripts/init_db.py

# Run migrations
uv run alembic upgrade head

# Generate synthetic data (optional)
uv run python scripts/generate_dataset.py

# Start backend server
uv run uvicorn backend.src.main:app --reload --port 8000
```

### 3. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

## Environment Variables

Create a `.env` file in the root directory:

```env
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/hospital_ai_assistant
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-4o-mini
JWT_SECRET_KEY=your_secret_key_change_this_in_production
```

## Usage

1. Start the backend server (port 8000)
2. Start the frontend dev server (port 3000)
3. Access the application at http://localhost:3000
4. Login as a patient (phone number) or service person (username/password)
5. Start a chat conversation with the AI assistant
6. The LLM will collect patient information and create tickets
7. Service persons can view and manage tickets from their dashboard

## API Endpoints

- `POST /api/auth/login` - Login for service persons/admins
- `POST /api/auth/login/patient` - Login for patients
- `POST /api/conversations` - Create new conversation
- `POST /api/conversations/{id}/messages` - Send message
- `GET /api/tickets` - List tickets
- `PUT /api/tickets/{id}/assign` - Assign ticket
- `PUT /api/tickets/{id}/status` - Update ticket status

## Features Implemented

✅ UV package management with pyproject.toml
✅ PostgreSQL database with SQLAlchemy models
✅ Alembic migrations
✅ JWT authentication for patients, service persons, and admins
✅ LangGraph conversation agent with persistent data collection
✅ Patient verification and history lookup
✅ Ticket creation with comprehensive patient information
✅ Appointment scheduling
✅ FastAPI REST API
✅ WebSocket support for real-time chat
✅ React + Tailwind frontend
✅ Patient and Service Person dashboards
✅ Synthetic data generation
