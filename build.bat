@echo off
cd /d "%~dp0"
python tools\build_vplus.py || goto :err
python tools\pack.py || goto :err
python tools\verify.py || goto :err
python tools\audit.py || goto :err
echo.
echo Build OK: output\VanillaPlus.sga   (run install.bat to copy it into CoH2)
pause
exit /b 0
:err
echo BUILD FAILED
pause
exit /b 1
