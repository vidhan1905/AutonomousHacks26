"""Script to create sequential_review_tickets table directly without Alembic."""
import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from backend.src.database.connection import engine


async def create_table():
    """Create sequential_review_tickets table directly."""
    print("Creating sequential_review_tickets table...")
    
    async with engine.begin() as conn:
        # Create sequential_review_tickets table
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS sequential_review_tickets (
                ticket_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                chain_id UUID NOT NULL UNIQUE REFERENCES sequential_review_chains(chain_id),
                conversation_id UUID NOT NULL REFERENCES conversations(conversation_id),
                patient_id UUID NOT NULL REFERENCES patients(patient_id),
                status VARCHAR NOT NULL DEFAULT 'step_pending',
                current_step_id UUID REFERENCES sequential_review_steps(step_id),
                description TEXT,
                llm_summary TEXT,
                patient_details JSONB,
                past_history_summary TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
                chain_completed_at TIMESTAMP
            );
        """))
        
        # Create indexes
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_sequential_review_ticket_chain 
            ON sequential_review_tickets(chain_id);
        """))
        
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_sequential_review_ticket_status 
            ON sequential_review_tickets(status);
        """))
        
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_sequential_review_ticket_current_step 
            ON sequential_review_tickets(current_step_id);
        """))
        
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_sequential_review_ticket_conversation 
            ON sequential_review_tickets(conversation_id);
        """))
        
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_sequential_review_ticket_patient 
            ON sequential_review_tickets(patient_id);
        """))
        
        print("✅ Sequential review tickets table created successfully!")
        print("   - sequential_review_tickets")


if __name__ == "__main__":
    asyncio.run(create_table())
