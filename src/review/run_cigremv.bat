@echo off
rem Full analysis of the four CIGRE MV relays (cigre_R1..R4, src/real_zone.py), relay front end, deterministic CNN.
rem Run from anywhere on the cigremv-cache branch, with the per-cubicle caches of build_cigremv_cache.py in
rem D:\evemt\cache. About 7-8 hours on the RTX 3050 Ti laptop: four adaptgrid_run invocations of ~1 h each,
rem one at a time, then the rules, seeds, reverse-held-out, Hasan SVM and directional-reverse runs.
rem TestGrid (adapt_A/B) results are never overwritten: every CIGRE output carries the relay name.
rem Everything goes to logs\run_cigremv.log; results to results\adaptgrid\*cigre*.json.
setlocal
cd /d "%~dp0\..\.."
set PYTHONIOENCODING=utf-8
set EVEMT_CACHE_DIRS=D:\evemt\cache
set LADDER_RSET=polcap
set OMP_NUM_THREADS=8
set MKL_NUM_THREADS=8
set OPENBLAS_NUM_THREADS=8
set LOG=logs\run_cigremv.log
if not exist logs mkdir logs
if not exist D:\evemt\cache (echo D:\evemt\cache not found: run build_cigremv_cache first. & exit /b 1)

git diff --quiet HEAD -- src tests || (echo Uncommitted changes under src\ or tests\: commit or stash first. & exit /b 1)
python -m pytest tests -q || exit /b 1

call :step python src\review\adaptgrid_run.py cigre_R1 --frontend relayfe || exit /b 1
call :step python src\review\adaptgrid_run.py cigre_R2 --frontend relayfe || exit /b 1
call :step python src\review\adaptgrid_run.py cigre_R3 --frontend relayfe || exit /b 1
call :step python src\review\adaptgrid_run.py cigre_R4 --frontend relayfe || exit /b 1
call :step python src\review\adaptgrid_rules.py cigre_R1 cigre_R2 cigre_R3 cigre_R4 --frontend relayfe || exit /b 1
call :step python src\review\adaptgrid_seeds.py --relay cigre_R1 --frontend relayfe || exit /b 1
call :step python src\review\adaptgrid_seeds.py --relay cigre_R2 --frontend relayfe || exit /b 1
call :step python src\review\adaptgrid_seeds.py --relay cigre_R3 --frontend relayfe || exit /b 1
call :step python src\review\adaptgrid_seeds.py --relay cigre_R4 --frontend relayfe || exit /b 1
call :step python src\review\adaptgrid_reverse_heldout.py --relays cigre_R1 cigre_R2 cigre_R3 cigre_R4 --frontend relayfe || exit /b 1
call :step python src\review\hasan_svm.py --relays cigre_R1 cigre_R2 cigre_R3 cigre_R4 --variants default sincos tunedC || exit /b 1
call :step python src\review\adaptgrid_directional_reverse.py --relays cigre_R1 cigre_R2 cigre_R3 cigre_R4 --frontend relayfe || exit /b 1
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
