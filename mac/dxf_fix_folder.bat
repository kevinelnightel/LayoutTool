@echo off
rem dxf_fix_folder.bat <folder> [lineweight]
rem Sequential clean of every *.dxf in <folder>: one dxf_fix.exe process per file,
rem so a bad file never stops the rest. Log: dxf_fix.log next to this script.
setlocal
if "%~1"=="" (
  echo usage: dxf_fix_folder.bat ^<folder^> [lineweight_0.01mm]
  exit /b 2
)
set "DIR=%~1"
set "LW=%~2"
set "N=0"
set "FAIL=0"
echo [folder] %DIR% >> "%~dp0dxf_fix.log"
for %%f in ("%DIR%\*.dxf") do (
  set /a N+=1
  if "%LW%"=="" (
    call "%~dp0dxf_fix.bat" "%%f"
  ) else (
    call "%~dp0dxf_fix.bat" "%%f" "%LW%"
  )
  if errorlevel 1 set /a FAIL+=1
)
echo [folder] done files=%N% failed=%FAIL% >> "%~dp0dxf_fix.log"
exit /b 0
