@echo off
rem Sample-size control for results/CIGREMV.md: the TestGrid CNN (adapt_A, adapt_B) trained with only 72
rem in-zone faults, three random draws, loading-bin folds (src/review/adaptgrid_subsample.py). About 35 min
rem on the RTX 3050 Ti laptop. Uses the TestGrid caches in data\. Log: logs\run_subsample.log;
rem result: results\adaptgrid\subsample_relayfe_cnn.json.
setlocal
cd /d "%~dp0\..\.."
set PYTHONIOENCODING=utf-8
set LADDER_RSET=polcap
set OMP_NUM_THREADS=8
set MKL_NUM_THREADS=8
set OPENBLAS_NUM_THREADS=8
set LOG=logs\run_subsample.log
if not exist logs mkdir logs

git diff --quiet HEAD -- src tests || (echo Uncommitted changes under src\ or tests\: commit or stash first. & exit /b 1)
python -m pytest tests -q || exit /b 1

echo === %date% %time% start >> %LOG%
echo [%time%] adaptgrid_subsample.py --relays adapt_A adapt_B --sizes 72 --draws 0 1 2
python src\review\adaptgrid_subsample.py --relays adapt_A adapt_B --sizes 72 --draws 0 1 2 >> %LOG% 2>&1
if errorlevel 1 (echo === %date% %time% FAILED >> %LOG% & echo FAILED - see %LOG% & exit /b 1)
echo === %date% %time% ALL DONE >> %LOG%
echo ALL DONE. Result in results\adaptgrid\subsample_relayfe_cnn.json, log in %LOG%.
exit /b 0
