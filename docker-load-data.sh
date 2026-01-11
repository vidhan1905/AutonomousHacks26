#!/bin/bash

# Docker Data Loading Script

set -e

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

echo "📦 Loading sample data into PostgreSQL..."

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

# Ensure checkpointer tables are set up
echo "🔧 Ensuring checkpointer tables are set up..."
docker compose exec -T backend python backend/scripts/setup_checkpointer.py || echo "⚠️  Checkpointer setup failed, but continuing..."

# Load data
echo "📊 Loading sample data..."
docker compose exec -T backend python scripts/generate_dataset.py

echo ""
echo "✅ Sample data loaded successfully!"
echo ""
echo "📋 Test credentials:"
echo "   Patient Phone: 001-852-326-5094x079"
echo "   Patient Name: April Maldonado"
echo "   Patient DOB: 1955-02-28"
echo ""
echo "   Service Person Username: blood_test_1 (or any service_type_1)"
echo "   Service Person Password: password123"
echo ""
echo "   Admin Username: admin_1"
echo "   Admin Password: admin123"
