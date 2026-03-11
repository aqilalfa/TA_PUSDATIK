import os
import shutil
from pathlib import Path

def cleanup():
    base_dir = Path(__file__).parent
    
    # Files to delete
    files_to_delete = [
        base_dir / "rag_system.db",
        base_dir / "langchain.db",
        base_dir / ".pytest_cache"
    ]
    
    for f in files_to_delete:
        try:
            if f.exists():
                if f.is_file():
                    f.unlink()
                    print(f"Deleted file: {f}")
                else:
                    shutil.rmtree(f)
                    print(f"Deleted dir: {f}")
        except Exception as e:
            print(f"Could not delete {f}: {e}")

    # Remove __pycache__
    for p in base_dir.rglob("__pycache__"):
        try:
            shutil.rmtree(p)
            print(f"Deleted __pycache__: {p}")
        except Exception as e:
            pass

if __name__ == "__main__":
    cleanup()
