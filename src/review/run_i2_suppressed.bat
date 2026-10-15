@echo off
rem Direction with inverters that suppress negative-sequence current, a model study on the CIGRE MV
rem relays R1-R4 (src/review/i2_suppressed_direction.py). CPU only, 10 worker processes; about
rem 15 min on the laptop. Needs the CIGRE cache in D:\evemt\cache. Log: logs\run_i2_suppressed.log;
rem result: results\cigremv\i2_suppressed_direction.json. One relay only: run_i2_suppressed.bat cigre_R1
setlocal
cd /d "%~dp0\..\.."
set PYTHONIOENCODING=utf-8
set EVEMT_CACHE_DIRS=D:\evemt\cache
set OMP_NUM_THREADS=1
set MKL_NUM_THREADS=1
set OPENBLAS_NUM_THREADS=1
set LOG=logs\run_i2_suppressed.log
if not exist logs mkdir logs
if not exist D:\evemt\cache (echo D:\evemt\cache not found. & exit /b 1)

git diff --quiet HEAD -- src tests || (echo Uncommitted changes under src\ or tests\: commit or stash first. & exit /b 1)
python -m pytest tests -q || exit /b 1

echo === %date% %time% start: i2_suppressed_direction.py %* >> %LOG%
echo [%time%] i2_suppressed_direction.py %*
python src\review\i2_suppressed_direction.py %* >> %LOG% 2>&1
if errorlevel 1 (echo === %date% %time% FAILED >> %LOG% & echo FAILED - see %LOG% & exit /b 1)
echo === %date% %time% ALL DONE >> %LOG%
echo ALL DONE. Result in results\cigremv\i2_suppressed_direction.json, log in %LOG%.
exit /b 0
