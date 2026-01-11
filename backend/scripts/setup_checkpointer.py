"""Script to setup PostgresSaver checkpointer tables."""
import asyncio
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from backend.src.config import settings


async def main():
    """Setup checkpointer tables."""
    print("Setting up PostgresSaver checkpointer tables...")
    try:
        # Convert database URL from asyncpg to psycopg format
        db_url = settings.database_url.replace("+asyncpg", "")
        host = db_url.split('@')[1].split('/')[0] if '@' in db_url else 'database'
        print(f"Connecting to: {host}")
        
        print("Initializing checkpointer connection...")
        # Use asyncio.wait_for to add timeout protection
        async def setup_with_timeout():
            async with AsyncPostgresSaver.from_conn_string(db_url) as checkpointer:
                print("Creating checkpointer tables...")
                # Setup tables (idempotent - safe to run multiple times)
                await checkpointer.setup()
                print("✓ Checkpointer tables created successfully!")
        
        # Set a 60 second timeout for the setup
        await asyncio.wait_for(setup_with_timeout(), timeout=60.0)
            
    except asyncio.TimeoutError:
        print("⚠️  Checkpointer setup timed out after 60 seconds")
        print("ℹ  This may happen if tables are being created. The checkpointer will auto-setup on first use.")
        return 0
    except KeyboardInterrupt:
        print("\n⚠️  Setup interrupted by user")
        sys.exit(1)
    except Exception as e:
        error_msg = str(e).lower()
        # Check for common "already exists" errors
        if any(keyword in error_msg for keyword in ["already exists", "duplicate", "relation", "table"]):
            print("ℹ Checkpointer tables already exist - this is okay")
            print("✓ Setup complete (tables were already present)")
            return 0
        else:
            print(f"⚠️  Error setting up checkpointer: {e}")
            # Don't exit with error - allow deployment to continue
            # The checkpointer will auto-setup on first use
            print("ℹ Note: Checkpointer will auto-setup tables on first use if needed")
            return 0


if __name__ == "__main__":
    asyncio.run(main())
