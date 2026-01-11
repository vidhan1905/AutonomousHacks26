"""Direct SQL migration script to update sequential_review_tickets table.

This script:
1. Adds step_id, step_index, and can_start columns
2. Migrates existing data from current_step_id to step_id
3. Drops the unique constraint on chain_id
4. Drops the old current_step_id column
"""
import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable not set")

# Convert SQLAlchemy URL format (postgresql+asyncpg://) to asyncpg format (postgresql://)
if DATABASE_URL.startswith("postgresql+asyncpg://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
elif DATABASE_URL.startswith("postgresql://"):
    pass  # Already correct
else:
    raise ValueError(f"Unsupported DATABASE_URL format: {DATABASE_URL}")


async def migrate():
    """Run the migration."""
    conn = await asyncpg.connect(DATABASE_URL)
    
    try:
        print("Starting migration: separate_tickets_per_step")
        
        # Check if step_id column already exists
        check_result = await conn.fetchval("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'sequential_review_tickets' 
            AND column_name = 'step_id'
        """)
        
        if check_result:
            print("Migration already applied - step_id column exists")
            return
        
        # Start transaction
        async with conn.transaction():
            print("1. Dropping unique constraint on chain_id...")
            try:
                await conn.execute("""
                    ALTER TABLE sequential_review_tickets 
                    DROP CONSTRAINT IF EXISTS sequential_review_tickets_chain_id_key
                """)
            except Exception as e:
                print(f"   Note: {e}")
            
            print("2. Adding new columns...")
            await conn.execute("""
                ALTER TABLE sequential_review_tickets 
                ADD COLUMN IF NOT EXISTS step_id UUID,
                ADD COLUMN IF NOT EXISTS step_index INTEGER,
                ADD COLUMN IF NOT EXISTS can_start BOOLEAN NOT NULL DEFAULT false
            """)
            
            print("3. Migrating existing data...")
            # Copy current_step_id to step_id
            await conn.execute("""
                UPDATE sequential_review_tickets
                SET step_id = current_step_id
                WHERE current_step_id IS NOT NULL
            """)
            
            # Set step_index based on step's index in chain
            await conn.execute("""
                UPDATE sequential_review_tickets srt
                SET step_index = srs.step_index
                FROM sequential_review_steps srs
                WHERE srt.step_id = srs.step_id
            """)
            
            # Set can_start = True for tickets where step_index matches chain's current_step_index
            await conn.execute("""
                UPDATE sequential_review_tickets srt
                SET can_start = true
                FROM sequential_review_chains src
                WHERE srt.chain_id = src.chain_id
                AND srt.step_index = src.current_step_index
            """)
            
            print("4. Deleting orphaned tickets (those without step_id)...")
            await conn.execute("""
                DELETE FROM sequential_review_tickets
                WHERE step_id IS NULL
            """)
            
            print("5. Making step_id non-nullable and adding unique constraint...")
            await conn.execute("""
                ALTER TABLE sequential_review_tickets
                ALTER COLUMN step_id SET NOT NULL
            """)
            
            await conn.execute("""
                ALTER TABLE sequential_review_tickets
                ADD CONSTRAINT uq_sequential_review_ticket_step UNIQUE (step_id)
            """)
            
            print("6. Making step_index non-nullable...")
            # Set default for any remaining null step_index values
            await conn.execute("""
                UPDATE sequential_review_tickets
                SET step_index = 0
                WHERE step_index IS NULL
            """)
            
            await conn.execute("""
                ALTER TABLE sequential_review_tickets
                ALTER COLUMN step_index SET NOT NULL
            """)
            
            print("7. Dropping old current_step_id column and index...")
            try:
                await conn.execute("""
                    DROP INDEX IF EXISTS ix_sequential_review_ticket_current_step
                """)
            except Exception as e:
                print(f"   Note: {e}")
            
            await conn.execute("""
                ALTER TABLE sequential_review_tickets
                DROP COLUMN IF EXISTS current_step_id
            """)
            
            print("8. Creating new indexes...")
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS ix_sequential_review_ticket_step 
                ON sequential_review_tickets (step_id)
            """)
            
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS ix_sequential_review_ticket_step_index 
                ON sequential_review_tickets (chain_id, step_index)
            """)
            
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS ix_sequential_review_ticket_can_start 
                ON sequential_review_tickets (can_start)
            """)
            
            print("✅ Migration completed successfully!")
            
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(migrate())
