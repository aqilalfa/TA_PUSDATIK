# Codebase Cleanup Implementation Plan

> **For Antigravity:** REQUIRED WORKFLOW: Use `.agent/workflows/execute-plan.md` to execute this plan in single-flow mode.

**Goal:** Clean up the Pusdatik codebase for stakeholders by removing unnecessary scripts, results, and metadata.

**Architecture:** Systematic deletion of identified files and directories using PowerShell commands.

**Tech Stack:** PowerShell, Git

---

### Task 1: Clean Root Summary and Artifact Files

**Files:**
- Delete: `FINAL_STATUS.md`, `IMPLEMENTATION_SUMMARY.md`, `PROGRESS_REPORT.md`, `SESSION_SUMMARY.md`, `SETUP_PROGRESS.md`, `STATUS_SISTEM.md`
- Delete: `smoke_check.bat`, `test_upload.py`, `trace_result.txt`, `nul`

**Step 1: Delete root markdown summaries**
Run: `powershell -Command "rm FINAL_STATUS.md, IMPLEMENTATION_SUMMARY.md, PROGRESS_REPORT.md, SESSION_SUMMARY.md, SETUP_PROGRESS.md, STATUS_SISTEM.md -ErrorAction SilentlyContinue"`

**Step 2: Delete root scripts and artifacts**
Run: `powershell -Command "rm smoke_check.bat, test_upload.py, trace_result.txt, nul -ErrorAction SilentlyContinue"`

**Step 3: Commit cleanup**
Run: `git add . ; git commit -m "chore: remove root summary files and test scripts"`

---

### Task 2: Clean Root Metadata and AI Directories

**Directories:**
- Delete: `.agent/`, `.claude/`, `.superpowers/`, `.planning/`, `edited/`, `.pytest_cache/`, `.ruff_cache/`

**Step 1: Delete directories**
Run: `powershell -Command "rm -Recurse -Force .agent, .claude, .superpowers, .planning, edited, .pytest_cache, .ruff_cache -ErrorAction SilentlyContinue"`

**Step 2: Commit cleanup**
Run: `git add . ; git commit -m "chore: remove AI metadata and temporary directories"`

---

### Task 3: Clean Backend Root Scripts and Temp Files

**Files:**
- Delete in `backend/`: `test_*.py`, `verify_*.py`, `_check_*.py`, `_test_*.py`, `check_chunks.py`, `cleanup.py`, `clear_db_cache.py`
- Delete in `backend/`: `_*.txt`, `_*.json`, `_*.log`, `*.log`
- Delete in `backend/`: `ind1.txt`, `pr_body.txt`, `standalone_out.txt`, `stats.txt`, `raw_se_text.txt`
- Delete in `backend/`: `test_*.txt`, `test_*.json`, `se_deep_result.json`, `se_verification_final.json`, `trace_out.json`, `trace_out.txt`
- Delete: `backend/requirements-dev.txt`, `backend/requirements-eval.txt`

**Step 1: Delete backend root python scripts**
Run: `powershell -Command "cd backend; rm test_*.py, verify_*.py, _check_*.py, _test_*.py, check_chunks.py, cleanup.py, clear_db_cache.py -ErrorAction SilentlyContinue"`

**Step 2: Delete backend temp data and logs**
Run: `powershell -Command "cd backend; rm _*.txt, _*.json, _*.log, *.log, ind1.txt, pr_body.txt, standalone_out.txt, stats.txt, raw_se_text.txt, test_*.txt, test_*.json, se_deep_result.json, se_verification_final.json, trace_out.json, trace_out.txt -ErrorAction SilentlyContinue"`

**Step 3: Delete backend dev requirements**
Run: `powershell -Command "cd backend; rm requirements-dev.txt, requirements-eval.txt -ErrorAction SilentlyContinue"`

**Step 4: Commit cleanup**
Run: `git add . ; git commit -m "chore: clean up backend root from test scripts and temp data"`

---

### Task 4: Clean Docs and Large Binaries

**Files/Directories:**
- Delete: `docs/WEEK2-3_SUMMARY.md`, `docs/evaluation/`, `docs/superpowers/`, `qdrant.zip`, `backend/OllamaSetup.exe`

**Step 1: Delete docs and root binaries**
Run: `powershell -Command "rm docs/WEEK2-3_SUMMARY.md, qdrant.zip -ErrorAction SilentlyContinue; rm -Recurse -Force docs/evaluation, docs/superpowers -ErrorAction SilentlyContinue"`

**Step 2: Delete backend binary**
Run: `powershell -Command "rm backend/OllamaSetup.exe -ErrorAction SilentlyContinue"`

**Step 3: Commit cleanup**
Run: `git add . ; git commit -m "chore: remove evaluation docs and large binaries"`

---

### Task 5: Frontend and Cache Cleanup

**Directories:**
- Delete: `frontend/dist/`, `backend/.pytest_cache/`

**Step 1: Delete frontend dist and backend cache**
Run: `powershell -Command "rm -Recurse -Force frontend/dist, backend/.pytest_cache -ErrorAction SilentlyContinue"`

**Step 2: Final Commit**
Run: `git add . ; git commit -m "chore: final cleanup of build artifacts and caches"`

---

### Task 6: Verification

**Step 1: List root directory**
Run: `ls`

**Step 2: List backend directory**
Run: `ls backend`

**Step 3: Verify core folders exist**
Expected: `backend/app` and `frontend/src` are present.
