# Docker Setup Guide

This guide explains how to containerize and run the Hospital AI Assistant application using Docker.

## Prerequisites

- Docker Engine 20.10+ (or Docker Desktop)
- Docker Compose 2.0+ (use `docker compose` not `docker-compose`)
- A `.env` file with required environment variables

## Quick Start

### Option 1: Using the Quick Start Script (Recommended)

1. **Run the setup script:**
   ```bash
   ./docker-start.sh
   ```
   
   This script will:
   - Create `.env` from `docker/env.example` if it doesn't exist
   - Build and start all Docker containers
   - Wait for PostgreSQL to be ready
   - Run database migrations

2. **Edit `.env` file** (if created automatically) with your actual values:
   - Set your `OPENAI_API_KEY`
   - Set a secure `JWT_SECRET_KEY` (use `openssl rand -hex 32` to generate one)
   - **IMPORTANT:** Ensure `DATABASE_URL` uses `postgres` as the hostname (not `localhost` or `db`)

### Option 2: Manual Setup

1. **Copy the environment file:**
   ```bash
   cp docker/env.example .env
   ```

2. **Edit `.env` file** with your actual values:
   - Set your `OPENAI_API_KEY`
   - Set a secure `JWT_SECRET_KEY` (use `openssl rand -hex 32` to generate one)
   - **IMPORTANT:** Ensure `DATABASE_URL` uses `postgres` as the hostname:
     ```
     DATABASE_URL=postgresql+asyncpg://postgres:postgres@postgres:5432/hospital_ai_assistant
     ```

3. **Build and start all services:**
   ```bash
   docker compose up -d --build
   ```

4. **Run database migrations:**
   ```bash
   docker compose exec -T backend alembic upgrade head
   ```

5. **Access the application:**
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - API Docs: http://localhost:8000/docs
   - Health Check: http://localhost:8000/health

## Environment Variables

The application uses the following environment variables (see `.env.example`):

### Database Configuration
- `DATABASE_URL`: PostgreSQL connection string 
  - **CRITICAL:** Must use `postgres` as hostname (Docker service name), not `localhost` or `db`
  - Format: `postgresql+asyncpg://username:password@postgres:5432/database_name`
  - Example: `postgresql+asyncpg://postgres:postgres@postgres:5432/hospital_ai_assistant`
- `POSTGRES_USER`: PostgreSQL username (default: postgres)
- `POSTGRES_PASSWORD`: PostgreSQL password (default: postgres)
- `POSTGRES_DB`: Database name (default: hospital_ai_assistant)
- `POSTGRES_PORT`: PostgreSQL port (default: 5432)

### OpenAI Configuration
- `OPENAI_API_KEY`: Your OpenAI API key
- `OPENAI_MODEL`: Model to use (default: gpt-4o-mini)
- `OPENAI_TEMPERATURE`: Temperature setting (default: 0.7)
- `OPENAI_MAX_TOKENS`: Max tokens (default: 2000)

### JWT Authentication
- `JWT_SECRET_KEY`: Secret key for JWT tokens (min 32 chars)
- `JWT_ALGORITHM`: JWT algorithm (default: HS256)
- `JWT_EXPIRATION_HOURS`: Token expiration time (default: 24)

### Server Configuration
- `BACKEND_PORT`: Backend server port (default: 8000)
- `FRONTEND_PORT`: Frontend server port (default: 3000)
- `VITE_API_URL`: API URL for frontend (default: http://localhost:8000)
- `CORS_ORIGINS`: Allowed CORS origins (comma-separated)

## Docker Services

### PostgreSQL Database
- **Service name:** `postgres`
- **Port:** 5432 (mapped to host)
- **Volume:** `postgres_data` (persistent storage)
- **Health check:** Enabled

### Backend API
- **Service name:** `backend`
- **Port:** 8000 (mapped to host)
- **Dependencies:** PostgreSQL (waits for health check)
- **Hot reload:** Enabled via volume mount (`./backend:/app/backend`)
- **Includes:** Alembic for database migrations

### Frontend
- **Service name:** `frontend`
- **Port:** 3000 (mapped to host, served via nginx)
- **Dependencies:** Backend
- **Nginx:** Configured for API proxying and WebSocket support

## Common Commands

### Start services
```bash
docker compose up -d
```

### Stop services
```bash
docker compose down
```

### View logs
```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f backend
docker compose logs -f frontend
docker compose logs -f postgres
```

### Rebuild after code changes
```bash
docker compose up -d --build
```

### Run database migrations
```bash
# Run migrations (non-interactive)
docker compose exec -T backend alembic upgrade head

# Or interactive mode
docker compose exec backend alembic upgrade head
```

**Note:** Migrations run automatically via the `docker-start.sh` script, but you may need to run them manually if:
- You're starting containers individually
- Database was recreated
- New migrations were added

### Create a new migration
```bash
docker compose exec backend alembic revision --autogenerate -m "description"
```

### Access backend shell
```bash
docker compose exec backend bash
```

### Access database
```bash
docker compose exec postgres psql -U postgres -d hospital_ai_assistant
```

### Clean up (removes containers, volumes, networks)
```bash
docker compose down -v
```

## Production Considerations

1. **Security:**
   - Change all default passwords
   - Use strong `JWT_SECRET_KEY`
   - Set proper `CORS_ORIGINS` for production domain
   - Use environment-specific `.env` files

2. **Performance:**
   - Remove volume mounts for production (line with `./backend:/app/backend`)
   - Use multi-stage builds (already implemented)
   - Configure nginx caching
   - Set up proper database connection pooling

3. **Monitoring:**
   - Add health check endpoints
   - Set up logging aggregation
   - Monitor resource usage

4. **Database:**
   - Set up regular backups
   - Use managed PostgreSQL service for production
   - Configure connection limits

## Troubleshooting

### Backend can't connect to database
**Symptoms:** Backend container keeps restarting, connection errors in logs

**Solutions:**
- **CRITICAL:** Check `DATABASE_URL` uses `postgres` as hostname (not `localhost` or `db`)
  ```bash
  # Check current DATABASE_URL
  docker compose exec backend env | grep DATABASE_URL
  
  # Should show: postgresql+asyncpg://...@postgres:5432/...
  # NOT: postgresql+asyncpg://...@localhost:5432/...
  # NOT: postgresql+asyncpg://...@db:5432/...
  ```
- Verify postgres service is healthy: `docker compose ps`
- Check postgres logs: `docker compose logs postgres`
- Recreate backend container to pick up new env vars:
  ```bash
  docker compose up -d --force-recreate backend
  ```

### Backend container restarting / Syntax errors
**Symptoms:** Container exits immediately, Python syntax errors in logs

**Solutions:**
- Check backend logs: `docker compose logs backend --tail 50`
- Common issues:
  - F-string syntax errors (backslashes in f-string expressions)
  - Missing imports or dependencies
- Rebuild backend: `docker compose up -d --build backend`

### Migration errors
**Symptoms:** `alembic upgrade head` fails with connection errors

**Solutions:**
- Ensure `DATABASE_URL` is correct (see above)
- Verify `alembic.ini` is copied to container:
  ```bash
  docker compose exec backend ls -la /app/alembic.ini
  ```
- Check database is accessible:
  ```bash
  docker compose exec backend python -c "from backend.src.config import settings; print(settings.database_url)"
  ```

### Frontend can't reach backend API
**Symptoms:** API calls fail, CORS errors

**Solutions:**
- Verify `VITE_API_URL` is set correctly in `.env` (used at build time)
- Check nginx configuration in `docker/nginx.conf`
- Ensure backend service is running: `docker compose ps`
- Rebuild frontend if API URL changed:
  ```bash
  docker compose up -d --build frontend
  ```

### Port already in use
**Symptoms:** `Error: bind: address already in use`

**Solutions:**
- Change ports in `.env` file:
  ```
  BACKEND_PORT=8001
  FRONTEND_PORT=3001
  ```
- Or stop conflicting services:
  ```bash
  # Find what's using the port (macOS/Linux)
  lsof -i :8000
  lsof -i :3000
  ```

### Build fails
**Symptoms:** Docker build errors, missing files

**Solutions:**
- Check Dockerfile syntax
- Verify all required files exist:
  - `README.md` (required by pyproject.toml)
  - `alembic.ini` (for migrations)
  - `pyproject.toml` (for dependencies)
- Check build logs: `docker compose build --no-cache backend`
- Verify `.dockerignore` isn't excluding needed files

### Docker command not found
**Symptoms:** `docker: command not found` or `docker-compose: command not found`

**Solutions:**
- Ensure Docker Desktop is running (macOS/Windows)
- Use `docker compose` (with space) not `docker-compose` (Docker Compose V2)
- Add Docker to PATH if needed:
  ```bash
  export PATH="/usr/local/bin:/Applications/Docker.app/Contents/Resources/bin:$PATH"
  ```

### TypeScript build errors
**Symptoms:** Frontend build fails with TypeScript errors

**Solutions:**
- Check `frontend/src/vite-env.d.ts` exists with proper type definitions
- Fix unused variable warnings (prefix with `_` or remove)
- Verify TypeScript config in `tsconfig.json`

## Development vs Production

### Development
- Volume mounts enabled for hot reload (`./backend:/app/backend`)
- Debug logging enabled
- Uses local `.env` file
- Development dependencies included
- Source code mounted for live editing

### Production
- Remove volume mounts from `docker-compose.yml`:
  ```yaml
  # Remove or comment out:
  # volumes:
  #   - ./backend:/app/backend
  ```
- Use environment variables from CI/CD or secrets management
- Enable production optimizations:
  - Set `PYTHONUNBUFFERED=0` for better logging
  - Configure proper logging levels
  - Enable nginx caching and compression
- Use managed database service (AWS RDS, Google Cloud SQL, etc.)
- Set up SSL/TLS certificates (use nginx or reverse proxy)
- Configure proper CORS origins for production domain
- Set up monitoring and alerting
- Use Docker secrets or environment variable injection
- Enable health checks and auto-restart policies

## File Structure

```
.
├── docker-compose.yml          # Main orchestration file
├── docker-start.sh             # Quick start script
├── docker/
│   ├── env.example            # Environment variables template
│   └── nginx.conf             # Nginx configuration for frontend
├── backend/
│   ├── Dockerfile             # Backend container definition
│   └── .dockerignore          # Files to exclude from backend build
├── frontend/
│   ├── Dockerfile             # Frontend container definition (multi-stage)
│   └── .dockerignore          # Files to exclude from frontend build
└── .dockerignore               # Root-level ignore patterns
```

## Additional Notes

- **Database Persistence:** Data is stored in Docker volume `postgres_data` and persists across container restarts
- **Network:** All services communicate via Docker network `hospital_ai_network`
- **Environment Variables:** Loaded from `.env` file in project root
- **Build Context:** Both Dockerfiles use project root as context (`.`)
- **Hot Reload:** Backend code changes are reflected immediately due to volume mount (development only)

## Quick Reference

### Check Status
```bash
docker compose ps                    # Show all containers
docker compose logs -f               # Follow all logs
docker compose logs backend --tail 50 # Last 50 lines of backend logs
```

### Restart Services
```bash
docker compose restart                # Restart all
docker compose restart backend        # Restart specific service
docker compose up -d --force-recreate backend  # Recreate container
```

### Database Operations
```bash
# Run migrations
docker compose exec -T backend alembic upgrade head

# Access database shell
docker compose exec postgres psql -U postgres -d hospital_ai_assistant

# Backup database
docker compose exec postgres pg_dump -U postgres hospital_ai_assistant > backup.sql

# Restore database
docker compose exec -T postgres psql -U postgres hospital_ai_assistant < backup.sql
```

### Clean Up
```bash
docker compose down                  # Stop and remove containers
docker compose down -v              # Remove containers and volumes (⚠️ deletes data)
docker compose down --rmi all        # Remove containers, volumes, and images
docker system prune                  # Clean up unused Docker resources
```

### Debugging
```bash
# Enter container shell
docker compose exec backend bash
docker compose exec frontend sh

# Check environment variables
docker compose exec backend env | grep DATABASE_URL

# Test database connection
docker compose exec backend python -c "from backend.src.config import settings; print(settings.database_url)"

# View container resource usage
docker stats
```
