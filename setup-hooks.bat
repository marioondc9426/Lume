@echo off
cd /d "%~dp0"
git config core.hooksPath .githooks
echo Pronto: a cada commit o Qwen.exe sera gerado por tras em dist\Qwen.exe (log em build\build.log).
pause
