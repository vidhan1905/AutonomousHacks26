#!/bin/bash

# Docker Checkpointer Setup Script

# Don't exit on error - we want to show the result even if it fails
set +e

# Ensure Docker is in PATH (for macOS Docker Desktop)
export PATH="/usr/local/bin:/Applications/Docker.app/Contents/Resources/bin:$PATH"

# Check if Docker is available
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not available. Please ensure Docker Desktop is running."
    echo "   You can start it from Applications or run: open -a Docker"
    exit 1
fi

# Check if Docker daemon is running
if ! docker info &> /dev/null; then
    echo "❌ Docker daemon is not running. Please start Docker Desktop."
    echo "   You can start it from Applications or run: open -a Docker"
    exit 1
fi

echo "🔧 Setting up PostgresSaver checkpointer tables..."

# Check if containers are running
if ! docker compose ps | grep -q "hospital_ai_backend.*Up"; then
    echo "❌ Backend container is not running. Please start it first:"
    echo "   docker compose up -d"
    exit 1
fi

# Check if database is ready
echo "⏳ Checking database connection..."
docker compose exec -T backend python -c "
import asyncio
from backend.src.database.connection import async_session_maker
async def check():
    async with async_session_maker() as session:
        await session.execute('SELECT 1')
asyncio.run(check())
" 2>/dev/null || {
    echo "⚠️  Database might not be ready. Waiting 5 seconds..."
    sleep 5
}

# Setup checkpointer tables
echo "📊 Creating checkpointer tables..."
echo "   Note: This may take 30-60 seconds on first run, or may auto-complete if tables exist"
echo ""

# Run the setup script (it has its own timeout handling)
docker compose exec -T backend python backend/scripts/setup_checkpointer.py

EXIT_CODE=$?

echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ Checkpointer setup completed!"
    echo ""
    echo "💡 The checkpointer is used by LangGraph to persist conversation state."
    echo "   This allows the AI to remember context across multiple messages."
else
    echo "⚠️  Checkpointer setup completed with warnings."
    echo "   This is usually okay - the checkpointer will auto-setup tables on first use."
    echo "   If you see errors above, check the database connection."
fi
