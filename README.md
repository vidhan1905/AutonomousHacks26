# Hospital AI Assistant System

AI-powered hospital assistant system with LangGraph MCP integration, real-time chat interface where LLM directly converses with patients, patient verification, ticket management, and appointment scheduling.

## Setup

1. **Install dependencies**: `uv sync`
2. **Configure environment variables**: 
   ```bash
   cp .env.example .env
   # Edit .env with your actual values
   ```
3. **Create database** (if it doesn't exist):
   ```bash
   uv run python scripts/init_db.py
   ```
4. **Run migrations**: `uv run alembic upgrade head`
5. **Generate synthetic data** (optional): `uv run python scripts/generate_dataset.py`
6. **Start backend**: `uv run uvicorn backend.src.main:app --reload --port 8000`
7. **Start frontend**: `cd frontend && npm install && npm run dev`

## Environment Variables

See `.env.example` for a sample configuration file. Copy it to `.env` and fill in your values:

- `DATABASE_URL`: PostgreSQL connection string
- `OPENAI_API_KEY`: Your OpenAI API key
- `JWT_SECRET_KEY`: A secure random string (use `openssl rand -hex 32` to generate)

## Quick Testing Guide

### Test Patient Account
- **Phone**: `001-852-326-5094x079`
- **Name**: April Maldonado
- **DOB**: 1955-02-28

### Quick Test Flow

1. **Login** as patient with phone: `001-852-326-5094x079`
2. **Start conversation** and send: `Hi`
3. **Provide info**: `My name is April Maldonado, 001-852-326-5094x079 and 1955-02-28`
4. **Request appointment**: `I'd like to schedule an appointment for next week`
5. **Request service**: `I need a blood test done`

### Example Test Messages

**For Appointment Scheduling:**
- `I'd like to schedule an appointment for next week for my follow-up`
- `Can I book a consultation?`
- `I want to see a doctor tomorrow`

**For Service Requests:**
- `I need a blood test done. I've been feeling tired lately`
- `Can you help me get a lab test?`
- `I need an imaging scan for my headaches`

**For Emergency:**
- `I'm having severe abdominal pain. I need emergency care`

For detailed testing instructions and all test scenarios, see [TESTING.md](./TESTING.md).
