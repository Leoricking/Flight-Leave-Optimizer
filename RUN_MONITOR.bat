@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist "data" mkdir "data"
where py >nul 2>nul
if %errorlevel%==0 (
 py -3 automation.py >> "data\scheduled_output.log" 2>&1
) else (
 python automation.py >> "data\scheduled_output.log" 2>&1
)
