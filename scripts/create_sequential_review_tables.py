"""Script to create sequential review tables directly without Alembic."""
import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from backend.src.database.connection import async_session_maker, engine
from backend.src.database.models import Base, SequentialReviewChain, SequentialReviewStep


async def create_tables():
    """Create sequential review tables directly."""
    print("Creating sequential review tables...")
    
    async with engine.begin() as conn:
        # Create sequential_review_chains table
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS sequential_review_chains (
                chain_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                conversation_id UUID NOT NULL REFERENCES conversations(conversation_id),
                patient_id UUID NOT NULL REFERENCES patients(patient_id),
                case_complexity_score INTEGER,
                complexity_reason TEXT,
                required_doctors_count INTEGER NOT NULL,
                current_step_index INTEGER NOT NULL DEFAULT 0,
                status VARCHAR NOT NULL DEFAULT 'pending',
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
                completed_at TIMESTAMP
            );
        """))
        
        # Create indexes for sequential_review_chains
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_sequential_review_chain_status 
            ON sequential_review_chains(status);
        """))
        
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_sequential_review_chain_current_step 
            ON sequential_review_chains(current_step_index);
        """))
        
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_sequential_review_chain_conversation 
            ON sequential_review_chains(conversation_id);
        """))
        
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_sequential_review_chain_patient 
            ON sequential_review_chains(patient_id);
        """))
        
        # Create sequential_review_steps table
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS sequential_review_steps (
                step_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                chain_id UUID NOT NULL REFERENCES sequential_review_chains(chain_id) ON DELETE CASCADE,
                step_index INTEGER NOT NULL,
                doctor_id UUID NOT NULL REFERENCES service_persons(service_person_id),
                ticket_id UUID REFERENCES tickets(ticket_id),
                status VARCHAR NOT NULL DEFAULT 'pending',
                review_notes TEXT,
                review_summary TEXT,
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                accumulated_context JSONB,
                UNIQUE(chain_id, step_index)
            );
        """))
        
        # Create indexes for sequential_review_steps
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_sequential_review_step_chain_index 
            ON sequential_review_steps(chain_id, step_index);
        """))
        
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_sequential_review_step_status 
            ON sequential_review_steps(status);
        """))
        
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_sequential_review_step_ticket 
            ON sequential_review_steps(ticket_id);
        """))
        
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_sequential_review_step_doctor 
            ON sequential_review_steps(doctor_id);
        """))
        
        # Add columns to tickets table if they don't exist
        await conn.execute(text("""
            DO $$ 
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name = 'tickets' AND column_name = 'sequential_review_chain_id'
                ) THEN
                    ALTER TABLE tickets 
                    ADD COLUMN sequential_review_chain_id UUID REFERENCES sequential_review_chains(chain_id);
                END IF;
            END $$;
        """))
        
        await conn.execute(text("""
            DO $$ 
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name = 'tickets' AND column_name = 'is_sequential_review'
                ) THEN
                    ALTER TABLE tickets 
                    ADD COLUMN is_sequential_review BOOLEAN NOT NULL DEFAULT false;
                END IF;
            END $$;
        """))
        
        # Create indexes for tickets sequential review fields
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_tickets_sequential_review_chain 
            ON tickets(sequential_review_chain_id);
        """))
        
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_tickets_is_sequential_review 
            ON tickets(is_sequential_review);
        """))
        
        print("✅ Sequential review tables created successfully!")
        print("   - sequential_review_chains")
        print("   - sequential_review_steps")
        print("   - Added columns to tickets table")


if __name__ == "__main__":
    asyncio.run(create_tables())
