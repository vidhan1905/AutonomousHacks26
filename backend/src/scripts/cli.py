"""CLI entry points for scripts."""
import asyncio
import sys
import importlib.util
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


def _load_module_from_file(script_path: Path, module_name: str):
    """Load a Python module from a file path."""
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load script: {script_path}")
    module = importlib.util.module_from_spec(spec)
    # Add project root to sys.path if not already there (scripts expect this)
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    spec.loader.exec_module(module)
    return module


def setup_checkpointer():
    """CLI entry point for setup_checkpointer."""
    try:
        script_path = project_root / "backend" / "scripts" / "setup_checkpointer.py"
        module = _load_module_from_file(script_path, "setup_checkpointer")
        result = asyncio.run(module.main())
        return result if result is not None else 0
    except Exception as e:
        print(f"Error running setup-checkpointer: {e}")
        import traceback
        traceback.print_exc()
        return 1


def init_db():
    """CLI entry point for init_db."""
    try:
        script_path = project_root / "scripts" / "init_db.py"
        module = _load_module_from_file(script_path, "init_db")
        asyncio.run(module.main())
        return 0  # If we reach here, main() completed successfully
    except SystemExit as e:
        # init_db.main() calls exit(1) on failure, which raises SystemExit
        return e.code if e.code is not None else 1
    except Exception as e:
        print(f"Error running init-db: {e}")
        import traceback
        traceback.print_exc()
        return 1


def insert_data():
    """CLI entry point for insert_generated_data."""
    try:
        script_path = project_root / "scripts" / "insert_generated_data.py"
        module = _load_module_from_file(script_path, "insert_generated_data")
        asyncio.run(module.main())
        return 0
    except Exception as e:
        print(f"Error running insert-data: {e}")
        import traceback
        traceback.print_exc()
        return 1


def setup():
    """CLI entry point for complete setup - runs init-db, setup-checkpointer, and insert-data in sequence."""
    print("=" * 70)
    print("Starting Complete Database Setup")
    print("=" * 70)
    print()
    
    # Step 1: Initialize database
    print("Step 1/3: Initializing database...")
    print("-" * 70)
    result = init_db()
    if result != 0:
        print(f"\n❌ Database initialization failed with exit code {result}")
        return result
    print("✓ Database initialized successfully")
    print()
    
    # Step 2: Setup checkpointer
    print("Step 2/3: Setting up checkpointer tables...")
    print("-" * 70)
    result = setup_checkpointer()
    if result != 0:
        print(f"\n⚠️  Checkpointer setup completed with warnings (exit code {result})")
        # Continue even if checkpointer setup has warnings (it's idempotent)
    else:
        print("✓ Checkpointer tables created successfully")
    print()
    
    # Step 3: Insert generated data
    print("Step 3/3: Inserting generated data...")
    print("-" * 70)
    result = insert_data()
    if result != 0:
        print(f"\n❌ Data insertion failed with exit code {result}")
        return result
    print("✓ Data inserted successfully")
    print()
    
    print("=" * 70)
    print("✓ Complete setup finished successfully!")
    print("=" * 70)
    return 0


def run_server():
    """CLI entry point for running the FastAPI backend server."""
    try:
        import uvicorn
        
        print("=" * 70)
        print("Starting Hospital AI Assistant Backend Server")
        print("=" * 70)
        print()
        print("📍 Server will be available at:")
        print("   API:      http://localhost:8000")
        print("   Docs:     http://localhost:8000/docs")
        print("   Health:   http://localhost:8000/health")
        print()
        print("Press Ctrl+C to stop the server")
        print("=" * 70)
        print()
        
        # Run uvicorn server with reload for development
        # Use import string format to enable reload functionality
        uvicorn.run(
            "backend.src.main:app",
            host="0.0.0.0",
            port=8000,
            reload=True,
            reload_dirs=[str(project_root / "backend")],
        )
        return 0
    except KeyboardInterrupt:
        print("\n\n✓ Server stopped by user")
        return 0
    except Exception as e:
        print(f"Error starting server: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m backend.src.scripts.cli <command>")
        print("Commands: setup, setup-checkpointer, init-db, insert-data, run")
        sys.exit(1)
    
    command = sys.argv[1]
    if command == "setup":
        sys.exit(setup())
    elif command == "setup-checkpointer":
        sys.exit(setup_checkpointer())
    elif command == "init-db":
        sys.exit(init_db())
    elif command == "insert-data":
        sys.exit(insert_data())
    elif command == "run" or command == "server":
        sys.exit(run_server())
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
