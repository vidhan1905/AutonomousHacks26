"""FastAPI main application."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.src.config import settings
from backend.src.api.routes import auth, conversations, tickets, appointments

app = FastAPI(title="Hospital AI Assistant API", version="0.1.0")

# CORS middleware
cors_origins_list = [origin.strip() for origin in settings.cors_origins.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(conversations.router)
app.include_router(tickets.router)
app.include_router(appointments.router)


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Hospital AI Assistant API", "version": "0.1.0"}


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}
