@echo off
REM Cross-platform stopper wrapper for Windows -> stop_all.py
setlocal
set "ROOT=%~dp0"
where py >nul 2>nul && (set "PY=py") || (set "PY=python")
"%PY%" "%ROOT%stop_all.py" %*
endlocal
