# Docker Setup Guide

Complete Docker deployment guide for the Hospital AI Assistant application.

## Prerequisites

- Docker Engine 20.10+ (or Docker Desktop)
- Docker Compose 2.0+ (use `docker compose` not `docker-compose`)

## Quick Start

**Just run one command:**

```bash
./docker-start.sh
```

That's it! The script handles everything automatically:
- Creates `.env` from `docker/env.example` if needed
- Builds and starts all Docker containers
- Waits for PostgreSQL to be ready
- Runs database migrations
- Sets up checkpointer tables (for LangGraph state persistence)
- Loads sample data into PostgreSQL
- Shows you access URLs and test credentials

### First Time Setup

1. **Run the deployment script:**
   ```bash
   ./docker-start.sh
   ```

2. **If `.env` was created automatically, edit it with your values:**
   - Set your `OPENAI_API_KEY`
   - Set a secure `JWT_SECRET_KEY` (use `openssl rand -hex 32` to generate one)
   - The script will wait for you to edit it before continuing

3. **Access the application:**
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - API Docs: http://localhost:8000/docs
   - Health Check: http://localhost:8000/health

## What Gets Deployed

The `./docker-start.sh` script automatically:

1. **Sets up the database** - Creates tables via migrations
2. **Configures checkpointer** - Sets up LangGraph state persistence tables
3. **Loads sample data** - Creates 500 patients, 54 service persons, 3 admins, and historical records

### Sample Data Includes

- **500 Patients** with realistic data (names, phone numbers, medical history, etc.)
- **54 Service Persons** (2-5 per service type) - Username: `{service_type}_1`, Password: `password123`
- **3 Admin Accounts** - Username: `admin_1`, Password: `admin123`
- **Patient History Records** - Historical visits for testing
- **Past Appointments** - Completed appointments for testing

### Test Credentials

After deployment completes, you'll see test credentials. Example:

- **Patient Login:**
  - Phone: `001-852-326-5094x079`
  - Name: April Maldonado
  - DOB: `1955-02-28`

- **Service Person Login:**
  - Username: `blood_test_1` (or any `{service_type}_1`)
  - Password: `password123`

- **Admin Login:**
  - Username: `admin_1`
  - Password: `admin123`

## Environment Variables

The application uses environment variables from `.env` file (see `docker/env.example`):

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
- `OPENAI_API_KEY`: Your OpenAI API key (required)
- `OPENAI_MODEL`: Model to use (default: gpt-4o-mini)
- `OPENAI_TEMPERATURE`: Temperature setting (default: 0.7)
- `OPENAI_MAX_TOKENS`: Max tokens (default: 2000)

### JWT Authentication
- `JWT_SECRET_KEY`: Secret key for JWT tokens (min 32 chars, required)
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
- **Credentials:** postgres/postgres (change in `.env` for production)

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

### Start/Stop Services
```bash
# Start everything (or use ./docker-start.sh for full deployment)
docker compose up -d

# Stop everything
docker compose down

# Restart services
docker compose restart

# Rebuild after code changes
docker compose up -d --build
```

### View Logs
```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f backend
docker compose logs -f frontend
docker compose logs -f postgres
```

### Database Operations
```bash
# Access database shell
docker compose exec postgres psql -U postgres -d hospital_ai_assistant

# PostgreSQL credentials:
# Username: postgres
# Password: postgres
# Database: hospital_ai_assistant
# Host (from containers): postgres
# Host (from host): localhost
# Port: 5432

# Verify data was loaded
docker compose exec postgres psql -U postgres -d hospital_ai_assistant -c "SELECT 'patients' as table_name, COUNT(*) FROM patients UNION ALL SELECT 'service_persons', COUNT(*) FROM service_persons UNION ALL SELECT 'admins', COUNT(*) FROM admins;"

# Backup database
docker compose exec postgres pg_dump -U postgres hospital_ai_assistant > backup.sql

# Restore database
docker compose exec -T postgres psql -U postgres hospital_ai_assistant < backup.sql

# Connect from host machine
psql -h localhost -U postgres -d hospital_ai_assistant
# Password: postgres
```

### Clean Up
```bash
# Stop and remove containers
docker compose down

# Remove containers, volumes, and networks (⚠️ deletes all data)
docker compose down -v
```

## Troubleshooting

### Backend can't connect to database
**Symptoms:** Backend container keeps restarting, connection errors in logs

**Solutions:**
- **CRITICAL:** Check `DATABASE_URL` uses `postgres` as hostname (not `localhost` or `db`)
  ```bash
  # Check current DATABASE_URL
  docker compose exec backend env | grep DATABASE_URL
  
  # Should show: postgresql+asyncpg://...@postgres:5432/...
  ```
- Verify postgres service is healthy: `docker compose ps`
- Check postgres logs: `docker compose logs postgres`
- Recreate backend container: `docker compose up -d --force-recreate backend`

### Backend container restarting / Syntax errors
**Symptoms:** Container exits immediately, Python syntax errors in logs

**Solutions:**
- Check backend logs: `docker compose logs backend --tail 50`
- Rebuild backend: `docker compose up -d --build backend`

### Port already in use
**Symptoms:** `Error: bind: address already in use`

**Solutions:**
- Change ports in `.env` file:
  ```
  BACKEND_PORT=8001
  FRONTEND_PORT=3001
  ```
- Or stop conflicting services

### Frontend can't reach backend API
**Symptoms:** API calls fail, CORS errors

**Solutions:**
- Verify `VITE_API_URL` is set correctly in `.env`
- Check nginx configuration in `docker/nginx.conf`
- Ensure backend service is running: `docker compose ps`
- Rebuild frontend: `docker compose up -d --build frontend`

### Docker command not found
**Symptoms:** `docker: command not found` or `docker-compose: command not found`

**Solutions:**
- Ensure Docker Desktop is running (macOS/Windows)
- Use `docker compose` (with space) not `docker-compose` (Docker Compose V2)
- Add Docker to PATH if needed

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

## File Structure

```
.
├── docker-compose.yml          # Main orchestration file
├── docker-start.sh              # Complete deployment script (use this!)
├── docker/
│   ├── env.example             # Environment variables template
│   └── nginx.conf              # Nginx configuration for frontend
├── backend/
│   ├── Dockerfile              # Backend container definition
│   └── .dockerignore           # Files to exclude from backend build
├── frontend/
│   ├── Dockerfile              # Frontend container definition (multi-stage)
│   └── .dockerignore           # Files to exclude from frontend build
└── .dockerignore                # Root-level ignore patterns
```

## Additional Notes

- **Database Persistence:** Data is stored in Docker volume `postgres_data` and persists across container restarts
- **Network:** All services communicate via Docker network `hospital_ai_network`
- **Environment Variables:** Loaded from `.env` file in project root
- **Build Context:** Both Dockerfiles use project root as context (`.`)
- **Hot Reload:** Backend code changes are reflected immediately due to volume mount (development only)
