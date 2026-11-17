@echo off
cd /d "%~dp0"
set "DEST=%USERPROFILE%\Documents\My Games\Company of Heroes 2\mods\tuning"
if not exist "%DEST%" mkdir "%DEST%"
copy /Y "output\VanillaPlus.sga" "%DEST%\VanillaPlus.sga"
echo Installed to %DEST%
echo In CoH2 pick tuning pack: "COH2 V+ Mod"
pause
