@echo off
rem B1 on longer lines: the delta screening with the protected line and the lines beyond it 2x and 3x
rem longer (src/review/b1_long_lines.py). CPU only, 10 worker processes; several hours, relays in the order
rem R3, R1, R4, R2, saved after each relay and scale. Needs the CIGRE cache in D:\evemt\cache.
rem Log: logs\run_b1_long_lines.log; result: results\cigremv\b1_long_lines.json.
rem One scale or relay only: run_b1_long_lines.bat 3 cigre_R3
setlocal
cd /d "%~dp0\..\.."
set PYTHONIOENCODING=utf-8
set EVEMT_CACHE_DIRS=D:\evemt\cache
set OMP_NUM_THREADS=1
set MKL_NUM_THREADS=1
set OPENBLAS_NUM_THREADS=1
set LOG=logs\run_b1_long_lines.log
if not exist logs mkdir logs
if not exist D:\evemt\cache (echo D:\evemt\cache not found. & exit /b 1)

git diff --quiet HEAD -- src tests || (echo Uncommitted changes under src\ or tests\: commit or stash first. & exit /b 1)
python -m pytest tests -q || exit /b 1

echo === %date% %time% start: b1_long_lines.py %* >> %LOG%
echo [%time%] b1_long_lines.py %*
python src\review\b1_long_lines.py %* >> %LOG% 2>&1
if errorlevel 1 (echo === %date% %time% FAILED >> %LOG% & echo FAILED - see %LOG% & exit /b 1)
echo === %date% %time% ALL DONE >> %LOG%
echo ALL DONE. Result in results\cigremv\b1_long_lines.json, log in %LOG%.
exit /b 0
