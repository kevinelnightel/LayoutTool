@echo off
rem ---------------------------------------------------------------------------
rem publish.bat - one click commit + push for LayoutTool
rem
rem   publish.bat                 -> commit with a timestamped message, then push
rem   publish.bat "your message"  -> commit with your message, then push
rem   publish.bat --check         -> only run the privacy guard, no commit/push
rem
rem Before committing it scans the tracked text files for personal identifiers
rem (user profile paths, mail domains, account ids) and aborts if it finds one,
rem so nothing private ends up in the public repository.
rem ---------------------------------------------------------------------------
setlocal enabledelayedexpansion
cd /d "%~dp0"

set "REMOTE=https://github.com/kevinelnightel/LayoutTool.git"
set "BRANCH=main"

echo [1/4] privacy guard
set "BAD="
set "PF=privacy_patterns.txt"
for /f "delims=" %%f in ('git ls-files "*.pmlobj" "*.pmlfrm" "*.mac" "*.md" "*.py" "*.bat" "*.txt" "*.pmlfnc"') do (
    rem the guard itself contains the patterns, so skip this script
    if /I not "%%f"=="publish.bat" (
        findstr /I /C:"\Users\" /C:"AppData\" "%%f" >nul 2>&1
        if not errorlevel 1 (
            echo    LEAK  %%f
            set "BAD=1"
        )
        if exist "%PF%" (
            for /f "usebackq delims=" %%p in ("%PF%") do (
                findstr /I /C:"%%p" "%%f" >nul 2>&1
                if not errorlevel 1 (
                    echo    LEAK  %%f  ^(pattern: %%p^)
                    set "BAD=1"
                )
            )
        )
    )
)
if defined BAD (
    echo.
    echo [ABORT] personal identifiers found above - edit those files first.
    exit /b 1
)
echo    clean

if /I "%~1"=="--check" (
    exit /b 0
)

echo [2/4] staging
if not exist ".git" (
    echo [ABORT] not a git repository here.
    exit /b 1
)
set "HASREMOTE="
git remote get-url origin >nul 2>&1
if errorlevel 1 (
    echo    adding remote origin
    git remote add origin "%REMOTE%"
)
git add -A

echo [3/4] commit
git diff --cached --quiet
if errorlevel 1 (
    if /I "%~1"=="-f" (
        git commit -q -F "publish.msg"
        if errorlevel 1 (
            echo [ABORT] commit failed - is publish.msg present?
            exit /b 1
        )
        echo    committed from publish.msg
    ) else (
        if "%~1"=="" (
            set "MSG=update %DATE% %TIME%"
        ) else (
            set "MSG=%~1"
        )
        git commit -q -m "!MSG!"
        if errorlevel 1 (
            echo [ABORT] commit failed.
            exit /b 1
        )
        echo    committed: !MSG!
    )
) else (
    echo    nothing new to commit
)

echo [4/4] push
git push origin %BRANCH%
if errorlevel 1 (
    echo [ABORT] push failed - check credentials or network.
    exit /b 1
)
echo.
echo done: https://github.com/kevinelnightel/LayoutTool
exit /b 0
