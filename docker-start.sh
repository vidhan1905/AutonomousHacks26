#!/bin/bash

# Docker Deployment Script
# Handles complete deployment: migrations, checkpointer setup, and data loading

# Don't exit on error - we want to continue even if some steps have issues
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
MAX_WAIT=30
WAIT_COUNT=0
while [ $WAIT_COUNT -lt $MAX_WAIT ]; do
    if docker compose exec -T postgres pg_isready -U postgres > /dev/null 2>&1; then
        echo "✓ PostgreSQL is ready!"
        break
    fi
    echo "   Waiting for PostgreSQL... ($WAIT_COUNT/$MAX_WAIT seconds)"
    sleep 2
    WAIT_COUNT=$((WAIT_COUNT + 2))
done

if [ $WAIT_COUNT -ge $MAX_WAIT ]; then
    echo "⚠️  PostgreSQL may not be ready, but continuing..."
fi

# Run complete setup using uv run setup
echo ""
echo "🔧 Running complete database setup (init-db, checkpointer, insert-data)..."
echo "   (This may take 30-60 seconds on first run...)"
if docker compose exec -T backend uv run setup; then
    echo "✓ Complete setup finished successfully"
    DATA_LOADED=true
else
    echo "⚠️  Setup had issues, but continuing..."
    DATA_LOADED=false
fi

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "✅ Deployment complete!"
echo "═══════════════════════════════════════════════════════════"
echo ""
echo "📍 Access the application:"
echo "   Frontend:    http://localhost:3000"
echo "   Backend API: http://localhost:8000"
echo "   API Docs:    http://localhost:8000/docs"
echo "   Health:      http://localhost:8000/health"
echo ""

if [ "$DATA_LOADED" = true ]; then
    echo "📋 Test Credentials:"
    echo "   Patient Login:"
    echo "     Phone: 001-852-326-5094x079"
    echo "     Name:  April Maldonado"
    echo "     DOB:   1955-02-28"
    echo ""
    echo "   Service Person Login:"
    echo "     Username: blood_test_1 (or any {service_type}_1)"
    echo "     Password: password123"
    echo ""
    echo "   Admin Login:"
    echo "     Username: admin_1"
    echo "     Password: admin123"
    echo ""
fi

echo "📋 Useful commands:"
echo "   View logs:    docker compose logs -f"
echo "   Stop:         docker compose down"
echo "   Restart:      docker compose restart"
echo "   Rebuild:      docker compose up -d --build"
echo ""
