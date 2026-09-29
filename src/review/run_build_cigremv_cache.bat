@echo off
rem One streaming pass over D:\evemt\adapt_grid-CigreMVGrid.tar.gz (68 GB), every cubicle cached to
rem D:\evemt\cache\adapt_grid-CigreMVGrid_cache.bin / .meta.npz (roughly 30-35 GB). About 1.5-2.5 hours.
rem Log: logs\build_cigremv_cache.log
setlocal
cd /d "%~dp0\..\.."
set PYTHONIOENCODING=utf-8
set LOG=logs\build_cigremv_cache.log
if not exist logs mkdir logs
echo === %date% %time% start >> %LOG%
echo [%time%] python src\build_cigremv_cache.py  (progress in %LOG%)
python -u src\build_cigremv_cache.py >> %LOG% 2>&1
if errorlevel 1 (echo === %date% %time% FAILED >> %LOG% & echo FAILED - see %LOG% & exit /b 1)
echo === %date% %time% ALL DONE >> %LOG%
echo ALL DONE. Cache in D:\evemt\cache\, log in %LOG%.
exit /b 0
