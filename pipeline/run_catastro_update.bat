@echo off
cd /d "C:\Users\ant\OneDrive\nealab\neahub\pipeline"
echo [%date% %time%] Starting catastro update...
python run_catastro_update.py >> output\catastro_update.log 2>&1
echo [%date% %time%] Catastro update finished (exit code %ERRORLEVEL%)
