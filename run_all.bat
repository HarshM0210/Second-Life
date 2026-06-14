@echo off
REM Cross-platform launcher wrapper for Windows -> run_all.py
setlocal
set "ROOT=%~dp0"
where py >nul 2>nul && (set "PY=py") || (set "PY=python")
"%PY%" "%ROOT%run_all.py" %*
endlocal
