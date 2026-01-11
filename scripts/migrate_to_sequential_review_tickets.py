"""Script to migrate existing sequential review tickets to SequentialReviewTicket model."""
import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from backend.src.database.connection import async_session_maker
from backend.src.database.models import (
    Ticket,
    SequentialReviewTicket,
    SequentialReviewChain,
    SequentialReviewStep,
)


async def migrate_tickets():
    """Migrate existing sequential review tickets to SequentialReviewTicket model."""
    print("Starting migration of sequential review tickets...")
    
    async with async_session_maker() as session:
        # Find all tickets with is_sequential_review = true
        tickets_result = await session.execute(
            select(Ticket).where(
                Ticket.is_sequential_review == True,
                Ticket.sequential_review_chain_id.isnot(None)
            )
        )
        tickets = tickets_result.scalars().all()
        
        print(f"Found {len(tickets)} sequential review tickets to migrate")
        
        migrated_count = 0
        skipped_count = 0
        error_count = 0
        
        for ticket in tickets:
            try:
                # Check if SequentialReviewTicket already exists for this chain
                existing_result = await session.execute(
                    select(SequentialReviewTicket).where(
                        SequentialReviewTicket.chain_id == ticket.sequential_review_chain_id
                    )
                )
                existing = existing_result.scalar_one_or_none()
                
                if existing:
                    print(f"  ⏭️  Skipping ticket {ticket.ticket_id} - SequentialReviewTicket already exists for chain {ticket.sequential_review_chain_id}")
                    skipped_count += 1
                    continue
                
                # Get chain to find current step
                chain_result = await session.execute(
                    select(SequentialReviewChain).where(
                        SequentialReviewChain.chain_id == ticket.sequential_review_chain_id
                    )
                )
                chain = chain_result.scalar_one_or_none()
                
                if not chain:
                    print(f"  ⚠️  Warning: Chain {ticket.sequential_review_chain_id} not found for ticket {ticket.ticket_id}")
                    error_count += 1
                    continue
                
                # Find current step based on chain's current_step_index
                current_step_id = None
                if chain.current_step_index is not None:
                    step_result = await session.execute(
                        select(SequentialReviewStep).where(
                            SequentialReviewStep.chain_id == chain.chain_id,
                            SequentialReviewStep.step_index == chain.current_step_index
                        )
                    )
                    step = step_result.scalar_one_or_none()
                    if step:
                        current_step_id = step.step_id
                
                # Determine status based on ticket and step status
                status = "step_pending"
                if current_step_id:
                    step_result = await session.execute(
                        select(SequentialReviewStep).where(
                            SequentialReviewStep.step_id == current_step_id
                        )
                    )
                    step = step_result.scalar_one_or_none()
                    if step:
                        if step.status == "completed":
                            # Check if all steps are completed
                            all_steps_result = await session.execute(
                                select(SequentialReviewStep).where(
                                    SequentialReviewStep.chain_id == chain.chain_id
                                )
                            )
                            all_steps = all_steps_result.scalars().all()
                            if all(s.status == "completed" for s in all_steps):
                                status = "chain_completed"
                            else:
                                status = "step_completed"
                        elif step.status == "in_review":
                            if ticket.status == "in_progress":
                                status = "step_in_progress"
                            elif ticket.status == "assigned":
                                status = "step_accepted"
                            else:
                                status = "step_pending"
                        elif step.status == "pending":
                            status = "step_pending"
                
                # Check if chain is cancelled
                if chain.status == "cancelled":
                    status = "chain_cancelled"
                elif chain.status == "completed":
                    status = "chain_completed"
                
                # Create SequentialReviewTicket
                sequential_ticket = SequentialReviewTicket(
                    chain_id=ticket.sequential_review_chain_id,
                    conversation_id=ticket.conversation_id,
                    patient_id=ticket.patient_id,
                    current_step_id=current_step_id,
                    description=ticket.description,
                    llm_summary=ticket.llm_summary,
                    patient_details=ticket.patient_details,
                    past_history_summary=ticket.past_history_summary,
                    status=status,
                )
                
                session.add(sequential_ticket)
                await session.commit()
                
                print(f"  ✅ Migrated ticket {ticket.ticket_id} -> SequentialReviewTicket {sequential_ticket.ticket_id} (status: {status})")
                migrated_count += 1
                
            except Exception as e:
                print(f"  ❌ Error migrating ticket {ticket.ticket_id}: {e}")
                import traceback
                traceback.print_exc()
                error_count += 1
                await session.rollback()
        
        print("\n" + "="*60)
        print("Migration Summary:")
        print(f"  ✅ Migrated: {migrated_count}")
        print(f"  ⏭️  Skipped: {skipped_count}")
        print(f"  ❌ Errors: {error_count}")
        print(f"  📊 Total processed: {len(tickets)}")
        print("="*60)


if __name__ == "__main__":
    asyncio.run(migrate_tickets())
