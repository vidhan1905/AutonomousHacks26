"""Script to setup PostgresSaver checkpointer tables."""
import asyncio
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from backend.src.agents.checkpointer import setup_checkpointer_tables


async def main():
    """Setup checkpointer tables."""
    print("Setting up PostgresSaver checkpointer tables...")
    try:
        await setup_checkpointer_tables()
        print("✓ Checkpointer tables created successfully!")
    except Exception as e:
        print(f"✗ Error setting up checkpointer: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    asyncio.run(main())
