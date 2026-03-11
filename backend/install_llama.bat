@echo off
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat"
cd /d D:\aqil\pusdatik\backend
set CMAKE_GENERATOR=Ninja
set CMAKE_ARGS=-DGGML_NATIVE=OFF
.\venv\Scripts\pip install llama-cpp-python --no-cache-dir --verbose
