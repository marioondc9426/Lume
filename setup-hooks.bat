@echo off
cd /d "%~dp0"
git config core.hooksPath .githooks
echo Pronto: a cada commit o Lume.exe sera gerado por tras em dist\Lume.exe (log em build\build.log).
pause
