"""Initialize database - create database if it doesn't exist."""
import asyncio
import asyncpg
from urllib.parse import urlparse
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/hospital_ai_assistant")


async def create_database_if_not_exists():
    """Create the database if it doesn't exist."""
    # Parse the database URL
    parsed = urlparse(DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://"))
    
    # Extract components
    user = parsed.username or "postgres"
    password = parsed.password or "postgres"
    host = parsed.hostname or "localhost"
    port = parsed.port or 5432
    database_name = parsed.path.lstrip("/") or "hospital_ai_assistant"
    
    print(f"Connecting to PostgreSQL server at {host}:{port}...")
    
    try:
        # Connect to PostgreSQL server (not to a specific database)
        # Use 'postgres' database which always exists
        admin_conn = await asyncpg.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database="postgres"  # Connect to default postgres database
        )
        
        # Check if database exists
        db_exists = await admin_conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1", database_name
        )
        
        if db_exists:
            print(f"Database '{database_name}' already exists.")
        else:
            print(f"Creating database '{database_name}'...")
            # Create database (note: CREATE DATABASE cannot be run in a transaction)
            await admin_conn.execute(f'CREATE DATABASE "{database_name}"')
            print(f"Database '{database_name}' created successfully!")
        
        await admin_conn.close()
        
        # Now test connection to the actual database
        print(f"Testing connection to '{database_name}'...")
        test_conn = await asyncpg.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database_name
        )
        await test_conn.close()
        print(f"Successfully connected to '{database_name}'!")
        
        return True
        
    except asyncpg.exceptions.InvalidPasswordError:
        print(f"Error: Invalid password for user '{user}'")
        print("Please check your DATABASE_URL in .env file")
        return False
    except asyncpg.exceptions.ConnectionDoesNotExistError:
        print(f"Error: Could not connect to PostgreSQL server at {host}:{port}")
        print("Please ensure PostgreSQL is running and accessible")
        return False
    except Exception as e:
        print(f"Error: {str(e)}")
        return False


async def main():
    """Main function."""
    print("=" * 60)
    print("Database Initialization Script")
    print("=" * 60)
    print()
    
    success = await create_database_if_not_exists()
    
    if success:
        print()
        print("=" * 60)
        print("Database initialization completed successfully!")
        print("You can now run migrations with: uv run alembic upgrade head")
        print("=" * 60)
    else:
        print()
        print("=" * 60)
        print("Database initialization failed!")
        print("Please check your PostgreSQL connection settings in .env")
        print("=" * 60)
        exit(1)


if __name__ == "__main__":
    asyncio.run(main())
