@echo off
setlocal enabledelayedexpansion

echo ============================================================
echo   Architecture Diagram Generator — Environment Setup
echo ============================================================
echo.

REM --- Step 1: Check Python --------------------------------------------------
python --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python is not installed or not on PATH.
    echo         Please install Python 3.10+ from https://python.org
    pause
    exit /b 1
)
echo [OK] Python found:
python --version

REM --- Step 2: Create virtual environment if missing --------------------------
set VENV_DIR=%~dp0venv
if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo.
    echo Creating virtual environment in venv\ ...
    python -m venv "%VENV_DIR%"
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] Failed to create venv.
        pause
        exit /b 1
    )
    echo [OK] Virtual environment created.
) else (
    echo [OK] Virtual environment already exists.
)

REM --- Step 3: Activate venv and install dependencies -------------------------
echo.
echo Installing Python dependencies from requirements.txt ...
call "%VENV_DIR%\Scripts\activate.bat"
python -m pip install --upgrade pip >nul 2>&1
pip install -r "%~dp0requirements.txt"
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)
echo [OK] Dependencies installed.

REM --- Step 4: Copy .env if missing -------------------------------------------
if not exist "%~dp0.env" (
    if exist "%~dp0.env.example" (
        copy "%~dp0.env.example" "%~dp0.env" >nul
        echo [OK] Created .env from .env.example — review it before running!
    )
) else (
    echo [OK] .env file already present.
)

REM --- Step 5: Verify tree-sitter grammars ------------------------------------
echo.
echo Verifying tree-sitter language grammars ...
python -c "import tree_sitter_java; print('  tree-sitter-java: OK')" 2>nul || echo [WARN] tree-sitter-java not found
python -c "import tree_sitter_python; print('  tree-sitter-python: OK')" 2>nul || echo [WARN] tree-sitter-python not found

REM --- Step 6: Summary --------------------------------------------------------
echo.
echo ============================================================
echo   SETUP COMPLETE!
echo ============================================================
echo.
echo   Start the desktop app:      run_app.bat
echo   Start the Streamlit UI:     venv\Scripts\python -m streamlit run src/main.py
echo   Run the demo pipeline:      venv\Scripts\python run_demo.py
echo.
echo   Make sure Ollama is running if you want AI enrichment:
echo       ollama pull phi3:mini
echo       ollama serve
echo.
pause
