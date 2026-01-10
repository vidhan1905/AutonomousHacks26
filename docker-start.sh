#!/bin/bash

# Docker Quick Start Script

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

echo "🚀 Starting Hospital AI Assistant with Docker..."

# Check if .env exists
if [ ! -f .env ]; then
    echo "📝 Creating .env file from docker/env.example..."
    cp docker/env.example .env
    echo "⚠️  Please edit .env file with your actual values before continuing!"
    echo "   Especially set your OPENAI_API_KEY and JWT_SECRET_KEY"
    read -p "Press Enter to continue after editing .env file..."
fi

# Build and start containers
echo "🔨 Building and starting Docker containers..."
docker compose up -d --build

# Wait for postgres to be ready
echo "⏳ Waiting for PostgreSQL to be ready..."
sleep 5

# Run migrations
echo "📊 Running database migrations..."
docker compose exec -T backend alembic upgrade head || echo "⚠️  Migration failed, but continuing..."

echo "✅ Setup complete!"
echo ""
echo "📍 Access the application:"
echo "   Frontend: http://localhost:3000"
echo "   Backend API: http://localhost:8000"
echo "   API Docs: http://localhost:8000/docs"
echo ""
echo "📋 Useful commands:"
echo "   View logs: docker compose logs -f"
echo "   Stop: docker compose down"
echo "   Restart: docker compose restart"
