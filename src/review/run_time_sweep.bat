@echo off
rem Decision-time sweep of the adapt_grid CNN (src/review/adaptgrid_time_sweep.py): 10, 15, 20, 30, 40 ms,
rem relays A and B, grouped and loqo, seeds 0 / 100 / 200. About 3.5 hours.
rem Output: results\adaptgrid\time_sweep_relayfe_cnn.json; log: logs\run_time_sweep.log
setlocal
cd /d "%~dp0\..\.."
set PYTHONIOENCODING=utf-8
set LADDER_RSET=polcap
set OMP_NUM_THREADS=8
set MKL_NUM_THREADS=8
set OPENBLAS_NUM_THREADS=8
set LOG=logs\run_time_sweep.log
if not exist logs mkdir logs
git diff --quiet HEAD -- src tests || (echo Uncommitted changes under src\ or tests\: commit or stash first. & exit /b 1)
python -m pytest tests\test_torch_det.py -q || exit /b 1
echo === %date% %time% start >> %LOG%
echo [%time%] python src\review\adaptgrid_time_sweep.py  (progress in %LOG%)
python -u src\review\adaptgrid_time_sweep.py >> %LOG% 2>&1
if errorlevel 1 (echo === %date% %time% FAILED >> %LOG% & echo FAILED - see %LOG% & exit /b 1)
echo === %date% %time% ALL DONE >> %LOG%
echo ALL DONE. Results in results\adaptgrid\time_sweep_relayfe_cnn.json, log in %LOG%.
exit /b 0
