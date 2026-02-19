@echo off
echo Starting Backend Server...
python -m uvicorn backend.main:app --reload
pause
