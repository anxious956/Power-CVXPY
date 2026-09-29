@echo off
rem B1 of the bridge review (review/bridge/LEAD_REVIEW.md): the delta-footprint screening on the CIGRE MV
rem study model, all four relays (src/review/b1_delta_screen.py). CPU only, 10 worker processes; about
rem 30-45 min on the laptop. Needs the CIGRE cache in D:\evemt\cache. Log: logs\run_b1.log;
rem result: results\cigremv\b1_delta_screen.json. One relay only: run_b1.bat cigre_R2
setlocal
cd /d "%~dp0\..\.."
set PYTHONIOENCODING=utf-8
set EVEMT_CACHE_DIRS=D:\evemt\cache
set OMP_NUM_THREADS=1
set MKL_NUM_THREADS=1
set OPENBLAS_NUM_THREADS=1
set LOG=logs\run_b1.log
if not exist logs mkdir logs
if not exist D:\evemt\cache (echo D:\evemt\cache not found. & exit /b 1)

git diff --quiet HEAD -- src tests || (echo Uncommitted changes under src\ or tests\: commit or stash first. & exit /b 1)
python -m pytest tests -q || exit /b 1

echo === %date% %time% start: b1_delta_screen.py %* >> %LOG%
echo [%time%] b1_delta_screen.py %*
python src\review\b1_delta_screen.py %* >> %LOG% 2>&1
if errorlevel 1 (echo === %date% %time% FAILED >> %LOG% & echo FAILED - see %LOG% & exit /b 1)
echo === %date% %time% ALL DONE >> %LOG%
echo ALL DONE. Result in results\cigremv\b1_delta_screen.json, log in %LOG%.
exit /b 0
