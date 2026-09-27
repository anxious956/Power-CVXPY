@echo off
rem Hasan et al. (2026) hierarchical linear-SVM relay on adapt_grid (src/review/hasan_svm.py), full run.
rem About 1 hour: relays A and B x variants default / pu / sincos / tunedC x 20 and 50 ms x grouped and
rem loqo, plus the installation-mismatch chain for the default variant.
rem Output: results\adaptgrid\hasan_svm_relayfe.json; log: logs\run_hasan_svm.log
setlocal
cd /d "%~dp0\..\.."
set PYTHONIOENCODING=utf-8
set LADDER_RSET=polcap
set OMP_NUM_THREADS=8
set MKL_NUM_THREADS=8
set OPENBLAS_NUM_THREADS=8
set LOG=logs\run_hasan_svm.log
if not exist logs mkdir logs
git diff --quiet HEAD -- src tests || (echo Uncommitted changes under src\ or tests\: commit or stash first. & exit /b 1)
python -m pytest tests\test_hasan_svm.py -q || exit /b 1
echo === %date% %time% start >> %LOG%
echo [%time%] python src\review\hasan_svm.py  (progress in %LOG%)
python -u src\review\hasan_svm.py >> %LOG% 2>&1
if errorlevel 1 (echo === %date% %time% FAILED >> %LOG% & echo FAILED - see %LOG% & exit /b 1)
echo === %date% %time% ALL DONE >> %LOG%
echo ALL DONE. Results in results\adaptgrid\hasan_svm_relayfe.json, log in %LOG%.
exit /b 0
