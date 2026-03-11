#!/usr/bin/env python3
"""
Full Reset Script
1. Backs up current data/documents
2. Syncs files from pusdatik/dokumen to data/documents (sorted by type)
3. Runs reingest_all.py
4. Runs fix_spbe_chunks.py
5. Runs add_bssn_audit_chunk.py
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

# Paths
BASE_DIR = Path(r"D:\aqil\pusdatik")
USER_DOCS_DIR = BASE_DIR / "dokumen"
SYSTEM_DOCS_DIR = BASE_DIR / "backend" / "data" / "documents" # Corrected path based on previous findings? 
# Wait, reingest_all.py default was "D:\aqil\pusdatik\data\documents"
# Step 713 showed d:\aqil\pusdatik\data exists. 
# Step 706 showed d:\aqil\pusdatik\backend\data exists too?
# Let's check where reingest_all.py points. Line 35: r"D:\aqil\pusdatik\data\documents"
# So I should use THAT one.

DATA_DIR = BASE_DIR / "data"
SYSTEM_DOCS_DIR = DATA_DIR / "documents"

BACKUP_DIR = DATA_DIR / "documents_backup"

def run_command(cmd, cwd=None):
    print(f"\n>>> Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd, shell=True)
    if result.returncode != 0:
        print(f"❌ Command failed with code {result.returncode}")
        sys.exit(result.returncode)
    print("✅ Success")

def sync_files():
    print(f"\n1. Syncing files from {USER_DOCS_DIR} to {SYSTEM_DOCS_DIR}")
    
    # 1. Backup
    if SYSTEM_DOCS_DIR.exists():
        if BACKUP_DIR.exists():
            shutil.rmtree(BACKUP_DIR)
        shutil.copytree(SYSTEM_DOCS_DIR, BACKUP_DIR)
        print(f"   Backed up to {BACKUP_DIR}")
        shutil.rmtree(SYSTEM_DOCS_DIR)
    
    # 2. Create structure
    (SYSTEM_DOCS_DIR / "peraturan").mkdir(parents=True)
    (SYSTEM_DOCS_DIR / "audit").mkdir(parents=True)
    (SYSTEM_DOCS_DIR / "others").mkdir(parents=True)
    
    # 3. Copy & Sort
    count = 0
    for file_path in USER_DOCS_DIR.glob("*"):
        if file_path.is_file() and file_path.suffix.lower() == ".pdf":
            name = file_path.name.lower()
            target_sub = "others"
            
            if any(k in name for k in ["peraturan", "pp ", "perpres", "permen", "uu ", "se ", "surat edaran"]):
                target_sub = "peraturan"
            elif any(k in name for k in ["laporan", "audit", "evaluasi"]):
                target_sub = "audit"
            
            shutil.copy2(file_path, SYSTEM_DOCS_DIR / target_sub / file_path.name)
            print(f"   Copied {file_path.name} -> {target_sub}")
            count += 1
            
    print(f"   Synced {count} files.")

def main():
    # Verify paths
    if not USER_DOCS_DIR.exists():
        print(f"❌ User docs dir not found: {USER_DOCS_DIR}")
        sys.exit(1)
        
    # 1. Sync
    sync_files()
    
    # Python executable
    python_exe = sys.executable
    script_dir = Path(__file__).parent
    backend_dir = script_dir.parent
    
    # 2. Re-ingest
    print("\n2. Re-ingesting all documents...")
    run_command([python_exe, str(script_dir / "reingest_all.py")], cwd=backend_dir)
    
    # 3. Fix chunks
    print("\n3. Fixing SPBE chunks...")
    run_command([python_exe, str(script_dir / "fix_spbe_chunks.py")], cwd=backend_dir)
    
    # 4. Add Audit chunk
    print("\n4. Adding Audit BSSN chunk...")
    run_command([python_exe, str(script_dir / "add_bssn_audit_chunk.py")], cwd=backend_dir)
    
    print("\n\n🎉 FULL RESET COMPLETE!")

if __name__ == "__main__":
    main()
