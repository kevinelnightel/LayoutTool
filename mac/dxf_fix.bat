@echo off
rem dxf_fix.bat - clean DXF export(s) in place. Everything resolves from %~dp0
rem (this file's own folder), so the folder can be moved as a whole.
rem
rem   Prefers the standalone dxf_fix.exe sitting next to this file (no Python
rem   needed on the machine). Falls back to python / dxf_fix.py if the exe is
rem   missing, so developing on this machine keeps working.
rem
rem   arg(s) given -> clean those files (multiple args allowed, handled in one
rem                   exe call so the process starts once)
rem   no arg       -> dxf_fix.exe reads dxf_fix_req.txt next to this script
rem
rem (PML SYSCOM cannot substitute $!vars, so the export path travels in the
rem  request file; see ERRORS E-18.)
setlocal
set "EXE=%~dp0dxf_fix.exe"
if exist "%EXE%" goto useexe

set "PY=python"
where python >nul 2>&1
if errorlevel 1 (
  if exist "E:\Program Files\Python312\python.exe" (
    set "PY=E:\Program Files\Python312\python.exe"
  ) else (
    echo [dxf_fix] neither dxf_fix.exe nor python found >> "%~dp0dxf_fix.log"
    exit /b 2
  )
)
if "%~1"=="" (
  "%PY%" "%~dp0dxf_fix.py" >> "%~dp0dxf_fix.log" 2>&1
) else (
  "%PY%" "%~dp0dxf_fix.py" %* >> "%~dp0dxf_fix.log" 2>&1
)
exit /b %ERRORLEVEL%

:useexe
if "%~1"=="" (
  "%EXE%" >> "%~dp0dxf_fix.log" 2>&1
) else (
  "%EXE%" %* >> "%~dp0dxf_fix.log" 2>&1
)
exit /b %ERRORLEVEL%
