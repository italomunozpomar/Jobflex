@ECHO OFF
ECHO #################################
ECHO #      JobFlex Run Script       #
ECHO #################################
ECHO.

REM Use %~dp0 to refer to the script's directory
SET "SCRIPT_DIR=%~dp0"

REM Check if venv directory exists in the script's directory
IF NOT EXIST "%SCRIPT_DIR%venv" (
    ECHO [+] Creating virtual environment...
    REM Using 'py -3' is often more reliable on Windows
    py -3 -m venv "%SCRIPT_DIR%venv"
    IF ERRORLEVEL 1 (
        ECHO [!] Failed to create virtual environment. Make sure Python is installed and in your PATH.
        PAUSE
        EXIT /B 1
    )
    ECHO.
    
    ECHO [+] Installing requirements...
    call "%SCRIPT_DIR%venv\Scripts\pip.exe" install -r "%SCRIPT_DIR%reqs.txt"
    IF ERRORLEVEL 1 (
        ECHO [!] Failed to install requirements.
        PAUSE
        EXIT /B 1
    )
    ECHO.

    ECHO [+] Installing Playwright browsers...
    call "%SCRIPT_DIR%venv\Scripts\python.exe" -m playwright install
    IF ERRORLEVEL 1 (
        ECHO [!] Failed to install Playwright browsers.
        PAUSE
        EXIT /B 1
    )
    ECHO.
    ECHO [+] Setup complete.
    ECHO.
)

REM Check if node_modules exists
IF NOT EXIST "%SCRIPT_DIR%node_modules" (
    ECHO [+] Installing Node.js dependencies...
    call npm install
    IF ERRORLEVEL 1 (
        ECHO [!] Failed to install Node.js dependencies. Make sure Node.js is installed.
        PAUSE
        EXIT /B 1
    )
    ECHO.
)

ECHO [+] Building Tailwind CSS...
call npm run build
IF ERRORLEVEL 1 (
    ECHO [!] Failed to build Tailwind CSS.
    PAUSE
    EXIT /B 1
)
ECHO.

ECHO [+] Starting Django development server...
ECHO    Access the application at http://127.0.0.1:8000/
ECHO    Press CTRL+C to stop the server.
ECHO.
call "%SCRIPT_DIR%venv\Scripts\python.exe" "%SCRIPT_DIR%Jobflex\manage.py" runserver

PAUSE
