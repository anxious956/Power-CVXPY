@echo off
rem Re-run every adapt_grid result that contains the CNN, with deterministic torch (src/torch_det.py).
rem Run from anywhere on the cnn-deterministic branch with the data caches in data\. About 9-10 hours on
rem the RTX 3050 Ti laptop: four adaptgrid_run invocations of ~2 h each, one at a time (four at once ran
rem out of memory on 2026-09-17), then the seed, reverse-held-out and split diagnostics (~1.5 h).
rem Old checkpoints and scores are moved aside, not deleted: the new code is refused against them.
rem Everything goes to logs\rerun_cnn_deterministic.log; results to results\adaptgrid\*.json.
setlocal
cd /d "%~dp0\..\.."
set PYTHONIOENCODING=utf-8
set LADDER_RSET=polcap
set OMP_NUM_THREADS=8
set MKL_NUM_THREADS=8
set OPENBLAS_NUM_THREADS=8
set LOG=logs\rerun_cnn_deterministic.log
if not exist logs mkdir logs

git diff --quiet HEAD -- src tests || (echo Uncommitted changes under src\ or tests\: commit or stash first. & exit /b 1)
python -m pytest tests\test_torch_det.py -q || exit /b 1

if exist logs\ckpt\adaptgrid   move logs\ckpt\adaptgrid   logs\ckpt\adaptgrid_before_determinism   >nul
if exist logs\scores\adaptgrid move logs\scores\adaptgrid logs\scores\adaptgrid_before_determinism >nul

call :step python src\review\adaptgrid_run.py adapt_A --frontend relayfe || exit /b 1
call :step python src\review\adaptgrid_run.py adapt_B --frontend relayfe || exit /b 1
call :step python src\review\adaptgrid_run.py adapt_A --frontend current || exit /b 1
call :step python src\review\adaptgrid_run.py adapt_B --frontend current || exit /b 1
call :step python src\review\adaptgrid_seeds.py --relay adapt_A --frontend relayfe || exit /b 1
call :step python src\review\adaptgrid_seeds.py --relay adapt_B --frontend relayfe || exit /b 1
call :step python src\review\adaptgrid_reverse_heldout.py --relays adapt_A adapt_B --frontend relayfe || exit /b 1
call :step python src\review\adaptgrid_splitdiag.py --relay adapt_A --frontend relayfe || exit /b 1
call :step python src\review\adaptgrid_splitdiag.py --relay adapt_B --frontend relayfe || exit /b 1
echo === %date% %time% tables >> %LOG%
python src\review\adaptgrid_tables.py > results\adaptgrid\TABLES.md 2>> %LOG% || exit /b 1
echo === %date% %time% ALL DONE >> %LOG%
echo ALL DONE. Results in results\adaptgrid\, log in %LOG%.
exit /b 0

:step
echo === %date% %time% start: %* >> %LOG%
echo [%time%] %*
%* >> %LOG% 2>&1
if errorlevel 1 (echo === %date% %time% FAILED: %* >> %LOG% & echo FAILED: %*  - see %LOG% & exit /b 1)
echo === %date% %time% end: %* >> %LOG%
exit /b 0
