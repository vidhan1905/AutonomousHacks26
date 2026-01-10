"""PostgresSaver checkpointer for LangGraph state persistence."""
import os
from typing import Optional
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from sqlalchemy import create_engine
from backend.src.config import settings


def create_checkpointer_sync() -> PostgresSaver:
    """Create synchronous PostgresSaver checkpointer."""
    db_url = settings.database_url.replace("+asyncpg", "")
    engine = create_engine(db_url, pool_pre_ping=True)
    return PostgresSaver(engine)


# Global checkpointer instance and context manager (lazy loaded)
_checkpointer: Optional[AsyncPostgresSaver] = None
_checkpointer_ctx = None  # Context manager to keep checkpointer alive


async def get_checkpointer() -> AsyncPostgresSaver:
    """Get or create checkpointer instance.
    
    ROOT CAUSE FIX: Create checkpointer once and reuse it.
    The context manager is kept alive globally for the lifetime of the application.
    """
    global _checkpointer, _checkpointer_ctx
    
    if _checkpointer is None:
        # AsyncPostgresSaver expects a connection string in psycopg format
        # Convert from asyncpg format: postgresql+asyncpg://... -> postgresql://...
        db_url = settings.database_url.replace("+asyncpg", "")
        
        # ROOT CAUSE FIX: from_conn_string returns an async context manager
        # We enter it once and keep both the context manager and instance alive
        ctx_manager = AsyncPostgresSaver.from_conn_string(db_url)
        _checkpointer = await ctx_manager.__aenter__()
        _checkpointer_ctx = ctx_manager  # Keep context manager alive
        
        # Setup tables if not already set up (idempotent)
        try:
            await _checkpointer.setup()
        except Exception:
            # Setup might fail if tables already exist - that's okay
            pass
    
    return _checkpointer


async def create_checkpointer_async() -> AsyncPostgresSaver:
    """Create asynchronous PostgresSaver checkpointer.
    
    DEPRECATED: Use get_checkpointer() instead for proper singleton pattern.
    Kept for backward compatibility.
    """
    return await get_checkpointer()


async def setup_checkpointer_tables():
    """Setup checkpointer tables in database."""
    checkpointer = await get_checkpointer()
    try:
        await checkpointer.setup()
    except Exception:
        # Setup might fail if tables already exist - that's okay
        pass
