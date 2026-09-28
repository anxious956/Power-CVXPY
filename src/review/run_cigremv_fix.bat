@echo off
rem Re-run what the mirrored cigre_R1 / cigre_R3 zone labels touched (fixed 28 Sep 2026: common.load_relay_adapt
rem now measures the zone from the relay, loc_rel). R2, R4 and TestGrid labels are unchanged, but the
rem multi-relay scripts are re-run on all four CIGRE relays so each output file stays one consistent run.
rem About 5.5 hours on the RTX 3050 Ti laptop. Old R1/R3 checkpoints and scores are moved aside, not deleted.
rem Resume after a failure with the step number: run_cigremv_fix.bat 4. Log: logs\run_cigremv_fix.log.
setlocal
set START=%~1
if "%START%"=="" set START=1
set STEP=0
cd /d "%~dp0\..\.."
set PYTHONIOENCODING=utf-8
set EVEMT_CACHE_DIRS=D:\evemt\cache
set LADDER_RSET=polcap
set OMP_NUM_THREADS=8
set MKL_NUM_THREADS=8
set OPENBLAS_NUM_THREADS=8
set LOG=logs\run_cigremv_fix.log
if not exist logs mkdir logs
if not exist D:\evemt\cache (echo D:\evemt\cache not found. & exit /b 1)

git diff --quiet HEAD -- src tests || (echo Uncommitted changes under src\ or tests\: commit or stash first. & exit /b 1)
python -m pytest tests -q || exit /b 1

for %%R in (cigre_R1 cigre_R3) do (
  if exist logs\ckpt\adaptgrid\%%R_relayfe if not exist logs\ckpt\adaptgrid\%%R_relayfe_mirrored_labels move logs\ckpt\adaptgrid\%%R_relayfe logs\ckpt\adaptgrid\%%R_relayfe_mirrored_labels >nul
  if exist logs\scores\adaptgrid\%%R_relayfe if not exist logs\scores\adaptgrid\%%R_relayfe_mirrored_labels move logs\scores\adaptgrid\%%R_relayfe logs\scores\adaptgrid\%%R_relayfe_mirrored_labels >nul
)

call :step python src\review\adaptgrid_run.py cigre_R1 --frontend relayfe || exit /b 1
call :step python src\review\adaptgrid_run.py cigre_R3 --frontend relayfe || exit /b 1
call :step python src\review\adaptgrid_rules.py cigre_R1 cigre_R2 cigre_R3 cigre_R4 --frontend relayfe || exit /b 1
call :step python src\review\adaptgrid_seeds.py --relay cigre_R1 --frontend relayfe || exit /b 1
call :step python src\review\adaptgrid_seeds.py --relay cigre_R3 --frontend relayfe || exit /b 1
call :step python src\review\adaptgrid_reverse_heldout.py --relays cigre_R1 cigre_R2 cigre_R3 cigre_R4 --frontend relayfe || exit /b 1
call :step python src\review\hasan_svm.py --relays cigre_R1 cigre_R2 cigre_R3 cigre_R4 --variants default sincos tunedC || exit /b 1
call :step python src\review\adaptgrid_directional_reverse.py --relays cigre_R1 cigre_R2 cigre_R3 cigre_R4 --frontend relayfe || exit /b 1
call :step python src\review\cigremv_diagnostics.py || exit /b 1
call :step python src\review\ibr_headroom.py || exit /b 1
call :step python src\review\cigremv_checks.py || exit /b 1
echo === %date% %time% tables >> %LOG%
python src\review\cigremv_tables.py > results\cigremv\TABLES.md 2>> %LOG% || exit /b 1
echo === %date% %time% ALL DONE >> %LOG%
echo ALL DONE. Log in %LOG%.
exit /b 0

:step
set /a STEP+=1
if %STEP% LSS %START% (echo [skip %STEP%] %* & exit /b 0)
echo === %date% %time% start (step %STEP%): %* >> %LOG%
echo [%time%] %*
%* >> %LOG% 2>&1
if errorlevel 1 (echo === %date% %time% FAILED: %* >> %LOG% & echo FAILED: %*  - see %LOG% & exit /b 1)
echo === %date% %time% end: %* >> %LOG%
exit /b 0
