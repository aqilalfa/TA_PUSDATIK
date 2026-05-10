# Design Doc: Codebase Cleanup for Stakeholders

**Date**: 2026-05-10
**Author**: Antigravity (AI Assistant)
**Status**: Approved

## 1. Overview
The goal of this task is to clean up the Pusdatik repository to prepare it for stakeholders. This involves removing unnecessary scripts, evaluation results, temporary files, and AI-specific metadata that clutter the codebase and are not required for production use.

## 2. Success Criteria
- The repository contains only essential source code, documentation, and configuration files.
- All standalone test scripts (`test_*.py`) in the root and backend root are removed.
- All temporary artifacts (`*.log`, `_*.txt`, `*.json` parsing results) are removed.
- Large binaries (`OllamaSetup.exe`, `qdrant.zip`) are removed.
- AI-specific metadata directories (`.agent`, `.claude`, etc.) are removed.
- The application remains functional and can be started via Docker or scripts.

## 3. Scope of Deletion

### 3.1 Root Directory
- **Delete**:
    - `FINAL_STATUS.md`
    - `IMPLEMENTATION_SUMMARY.md`
    - `PROGRESS_REPORT.md`
    - `SESSION_SUMMARY.md`
    - `SETUP_PROGRESS.md`
    - `STATUS_SISTEM.md`
    - `qdrant.zip`
    - `smoke_check.bat`
    - `test_upload.py`
    - `trace_result.txt`
    - `nul`
    - `.agent/`
    - `.claude/`
    - `.superpowers/`
    - `.planning/`
    - `edited/`
    - `.pytest_cache/`
    - `.ruff_cache/`

### 3.2 Backend Directory
- **Delete**:
    - `backend/test_*.py` (root of backend only)
    - `backend/verify_*.py`
    - `backend/_check_*.py`
    - `backend/_test_*.py`
    - `backend/check_chunks.py`
    - `backend/cleanup.py`
    - `backend/clear_db_cache.py`
    - `backend/_*.txt`, `backend/_*.json`, `backend/_*.log`
    - `backend/*.log`
    - `backend/OllamaSetup.exe`
    - `backend/requirements-dev.txt`
    - `backend/requirements-eval.txt`
    - `backend/ind1.txt`, `backend/pr_body.txt`, `backend/standalone_out.txt`, `backend/stats.txt`, `backend/raw_se_text.txt`
    - `backend/test_*.txt`, `backend/test_*.json`
    - `backend/se_deep_result.json`, `backend/se_verification_final.json`, `backend/trace_out.json`, `backend/trace_out.txt`
    - `backend/.pytest_cache/`

### 3.3 Docs Directory
- **Delete**:
    - `docs/WEEK2-3_SUMMARY.md`
    - `docs/evaluation/`
    - `docs/superpowers/`

### 3.4 Frontend Directory
- **Delete**:
    - `frontend/dist/`

## 4. Implementation Strategy
We will use a series of `run_command` calls to delete the specified files and directories. Since many deletions involve patterns (like `test_*.py`), we will use PowerShell commands to handle them safely.

## 5. Verification
- Verify that the `backend/app` and `frontend/src` directories are intact.
- Verify that `README.md` and `QUICKSTART.md` still exist.
- Run a simple check to ensure no large files like `.exe` or `.zip` remain in the core folders.
