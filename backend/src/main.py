"""FastAPI main application."""
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.src.config import settings
from backend.src.api.routes import auth, conversations, tickets, appointments, patients, sequential_reviews, sequential_review_tickets

# Initialize LangSmith tracing if enabled
if settings.langsmith_tracing and settings.langsmith_api_key:
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_API_KEY"] = settings.langsmith_api_key
    if settings.langsmith_project:
        os.environ["LANGCHAIN_PROJECT"] = settings.langsmith_project
    print(f"[LANGSMITH] Tracing enabled for project: {settings.langsmith_project}")
elif settings.langsmith_api_key:
    # If API key is set but tracing is disabled, warn
    print("[LANGSMITH] API key provided but tracing is disabled. Set langsmith_tracing=true to enable.")
else:
    print("[LANGSMITH] Tracing disabled. Set langsmith_api_key and langsmith_tracing=true to enable.")

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
app.include_router(patients.router)
app.include_router(sequential_reviews.router)
app.include_router(sequential_review_tickets.router)


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Hospital AI Assistant API", "version": "0.1.0"}


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}
