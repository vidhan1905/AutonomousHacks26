"""Initialize database - create database if it doesn't exist and create all tables."""
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
from sqlalchemy.ext.asyncio import create_async_engine

# Import all models to register them with Base.metadata
from backend.src.database.connection import Base
from backend.src.database.models import (
    Patient, Admin, ServicePerson, Conversation,
    Ticket, Appointment, PatientHistory, TicketUpdate,
    DoctorExpertise, DoctorCaseHistory, TicketAssignment, PatientHistorySummary
)

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
    
    # Show connection info (mask password)
    masked_url = DATABASE_URL
    if "@" in masked_url and ":" in masked_url.split("@")[0]:
        # Mask password in URL
        parts = masked_url.split("@")
        if len(parts) == 2:
            auth_part = parts[0]
            if ":" in auth_part:
                user_part = auth_part.split(":")[0]
                masked_url = f"{user_part}:***@{parts[1]}"
    
    print(f"Using DATABASE_URL: {masked_url}")
    print(f"Connecting to PostgreSQL server at {host}:{port} as user '{user}'...")
    
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
        print(f"❌ Error: Invalid password for user '{user}'")
        print()
        print("Please check your DATABASE_URL in .env file")
        print()
        print("Expected format:")
        print("  DATABASE_URL=postgresql+asyncpg://username:password@host:port/database_name")
        print()
        print("Example:")
        print("  DATABASE_URL=postgresql+asyncpg://postgres:your_password@localhost:5432/hospital_ai_assistant")
        print()
        print("To fix this:")
        print("  1. Check your PostgreSQL password (default is often 'postgres' if you haven't changed it)")
        print("  2. Update the .env file with the correct password")
        print("  3. If you don't know your PostgreSQL password, you can:")
        print("     - Reset it in PostgreSQL configuration")
        print("     - Or use a different user with correct credentials")
        print()
        return False
    except asyncpg.exceptions.ConnectionDoesNotExistError:
        print(f"❌ Error: Could not connect to PostgreSQL server at {host}:{port}")
        print()
        print("Please ensure:")
        print("  1. PostgreSQL is installed and running")
        print("  2. PostgreSQL is accessible at the specified host and port")
        print("  3. Your DATABASE_URL in .env file is correct")
        print()
        print("To check if PostgreSQL is running:")
        print("  - Windows: Check Services or run 'pg_ctl status'")
        print("  - Linux/Mac: Run 'sudo systemctl status postgresql' or 'brew services list'")
        print()
        return False
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Error: {error_msg}")
        print()
        if "password" in error_msg.lower() or "authentication" in error_msg.lower():
            print("This appears to be an authentication error.")
            print("Please check your DATABASE_URL in .env file and ensure:")
            print("  - Username is correct")
            print("  - Password is correct")
            print("  - Database exists or can be created")
            print()
        return False


async def create_tables():
    """Create all tables using SQLAlchemy."""
    print("Creating database tables...")
    try:
        engine = create_async_engine(DATABASE_URL, echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await engine.dispose()
        print("All tables created successfully!")
        return True
    except Exception as e:
        print(f"Error creating tables: {str(e)}")
        return False


async def add_missing_columns():
    """Add missing columns to existing tables (idempotent)."""
    parsed = urlparse(DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://"))
    user = parsed.username or "postgres"
    password = parsed.password or "postgres"
    host = parsed.hostname or "localhost"
    port = parsed.port or 5432
    database_name = parsed.path.lstrip("/") or "hospital_ai_assistant"
    
    try:
        conn = await asyncpg.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database_name
        )
        
        print("Checking for missing columns in existing tables...")
        
        # Check and add columns to service_persons table
        columns_to_add = [
            ("service_persons", "current_workload", "INTEGER NOT NULL DEFAULT 0"),
            ("service_persons", "max_workload", "INTEGER NOT NULL DEFAULT 10"),
            ("service_persons", "max_daily_appointments", "INTEGER NOT NULL DEFAULT 15"),
            ("service_persons", "workload_updated_at", "TIMESTAMP"),
            ("service_persons", "is_available", "BOOLEAN NOT NULL DEFAULT true"),
        ]
        
        # Check and add columns to tickets table
        columns_to_add.extend([
            ("tickets", "assignment_status", "VARCHAR NOT NULL DEFAULT 'unassigned'"),
            ("tickets", "offered_to_count", "INTEGER NOT NULL DEFAULT 0"),
            ("tickets", "accepted_by", "UUID"),
            ("tickets", "accepted_at", "TIMESTAMP"),
        ])
        
        for table_name, column_name, column_def in columns_to_add:
            # Check if column exists
            column_exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT 1 
                    FROM information_schema.columns 
                    WHERE table_name = $1 AND column_name = $2
                )
            """, table_name, column_name)
            
            if not column_exists:
                try:
                    # For foreign key columns, add the column first, then the constraint
                    if column_name == "accepted_by":
                        await conn.execute(f"""
                            ALTER TABLE {table_name} 
                            ADD COLUMN {column_name} {column_def}
                        """)
                        # Add foreign key constraint
                        await conn.execute(f"""
                            ALTER TABLE {table_name}
                            ADD CONSTRAINT fk_{table_name}_{column_name}
                            FOREIGN KEY ({column_name}) 
                            REFERENCES service_persons(service_person_id)
                        """)
                        print(f"  Added column {column_name} to {table_name} with foreign key")
                    else:
                        await conn.execute(f"""
                            ALTER TABLE {table_name} 
                            ADD COLUMN {column_name} {column_def}
                        """)
                        print(f"  Added column {column_name} to {table_name}")
                except Exception as e:
                    # Column might have been added by another process, ignore
                    if "already exists" not in str(e).lower() and "duplicate" not in str(e).lower():
                        print(f"  Warning: Could not add {column_name} to {table_name}: {str(e)}")
        
        # Create indexes for new columns if they don't exist
        indexes_to_create = [
            ("service_persons", "ix_service_persons_current_workload", "current_workload"),
            ("service_persons", "ix_service_persons_is_available", "is_available"),
            ("service_persons", "ix_service_persons_max_daily_appointments", "max_daily_appointments"),
            ("service_persons", "ix_service_persons_service_type_available_workload", 
             "service_type, is_available, current_workload"),
            ("tickets", "ix_tickets_assignment_status", "assignment_status"),
            ("tickets", "ix_tickets_accepted_by", "accepted_by"),
        ]
        
        for table_name, index_name, columns in indexes_to_create:
            index_exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT 1 
                    FROM pg_indexes 
                    WHERE tablename = $1 AND indexname = $2
                )
            """, table_name, index_name)
            
            if not index_exists:
                try:
                    await conn.execute(f"""
                        CREATE INDEX {index_name} 
                        ON {table_name} ({columns})
                    """)
                    print(f"  Created index {index_name} on {table_name}")
                except Exception as e:
                    if "already exists" not in str(e).lower():
                        print(f"  Warning: Could not create index {index_name}: {str(e)}")
        
        await conn.close()
        print("Column and index checks completed!")
        return True
        
    except Exception as e:
        print(f"Error adding missing columns: {str(e)}")
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
        # Create all tables
        tables_created = await create_tables()
        
        if tables_created:
            # Add missing columns to existing tables
            await add_missing_columns()
            
            print()
            print("=" * 60)
            print("Database initialization completed successfully!")
            print("All tables and columns are ready to use.")
            print("=" * 60)
        else:
            print()
            print("=" * 60)
            print("Warning: Some tables may not have been created.")
            print("Please check the error messages above.")
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
