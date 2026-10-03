@echo off
rem Practice mode: runs Talanta Soka on this laptop with demo accounts (password Demo#2026).
rem The live site and live database are never touched. Close this window to stop.
set DATABASE_URL=sqlite:///practice.sqlite3
set R2_BUCKET_NAME=off
set DJANGO_EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"
set PY=python
if exist "..\.venv\Scripts\python.exe" set PY=..\.venv\Scripts\python.exe
%PY% manage.py migrate --noinput
%PY% manage.py seed_demo
echo.
echo Open http://127.0.0.1:8000 in your browser.
%PY% manage.py runserver
