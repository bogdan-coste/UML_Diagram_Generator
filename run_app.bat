@echo off
REM Launch the Architecture Diagram Generator desktop app using the venv
call "%~dp0venv\Scripts\activate.bat"
python -m src.desktop_app
